# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import os
from pathlib import Path

from aws_cdk import Aws, CfnOutput, CustomResource, Duration, RemovalPolicy
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as cloudfront_origins
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_efs as efs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda
from aws_cdk import aws_s3 as s3
from aws_cdk.aws_lambda import LayerVersion, Code, Runtime
from aws_cdk.aws_ecr_assets import DockerImageAsset, Platform
from aws_lambda_layers.aws_solutions.layer import SolutionsLayer
from aws_solutions.cdk.aws_lambda.layers.aws_lambda_powertools import PowertoolsLayer
from aws_solutions.cdk.aws_lambda.python.function import SolutionsPythonFunction
from aws_solutions.cdk.stack import SolutionStack
from constructs import Construct

import prebid_server.stack_constants as globals

from .prebid_datasync_constructs import EfsCleanup, DataSyncTask, DataSyncMonitoring
from .prebid_glue_constructs import GlueEtl
from .prebid_artifacts_constructs import ArtifactsManager
from .cloudtrail_construct import CloudTrailConstruct
from .cloudwatch_metrics_construct import CloudwatchMetricsConstruct
from .operational_metrics_construct import OperationalMetricsConstruct
from .cloudwatch_alarms_construct import CloudwatchAlarms
from .alb_access_logs_construct import AlbAccessLogsConstruct

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ECR_REPO_NAME = os.getenv("ECR_REPO_NAME") or "prebid-server"
PUBLIC_ECR_REGISTRY = os.getenv("PUBLIC_ECR_REGISTRY")
ECR_REPO_TAG = os.getenv("PUBLIC_ECR_TAG") or "latest"
ECR_REGISTRY = os.getenv("OVERRIDE_ECR_REGISTRY")
if not ECR_REGISTRY and (PUBLIC_ECR_REGISTRY and ECR_REPO_TAG):
    ECR_REGISTRY = f"{PUBLIC_ECR_REGISTRY}/{ECR_REPO_NAME}:{ECR_REPO_TAG}"
    logger.debug(f"ECR_REGISTRY: {ECR_REGISTRY}")


class PrebidServerStack(SolutionStack):
    name = "prebid-server-deployment-on-aws"
    description = "Prebid Server Deployment on AWS"
    template_filename = "prebid-server-deployment-on-aws.template"

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.synthesizer.bind(self)

        # Custom resource for Cloudfront header secret
        header_secret_gen_function = SolutionsPythonFunction(
            self,
            "HeaderSecretGenFunction",
            globals.CUSTOM_RESOURCES_PATH
            / "header_secret_lambda"
            / "header_secret_gen.py",
            "event_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            description="Lambda function for header secret generation",
            timeout=Duration.minutes(1),
            memory_size=256,
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[
                PowertoolsLayer.get_or_create(self),
                SolutionsLayer.get_or_create(self),
            ],
        )

        header_secret_gen_function.add_environment(
            "SOLUTION_ID", self.node.try_get_context("SOLUTION_ID")
        )
        header_secret_gen_function.add_environment(
            "SOLUTION_VERSION", self.node.try_get_context("SOLUTION_VERSION")
        )

        header_secret_gen_custom_resource = CustomResource(
            self,
            "HeaderSecretGenCr",
            service_token=header_secret_gen_function.function_arn,
            properties={},
        )

        x_header_secret_value = header_secret_gen_custom_resource.get_att_string(
            "header_secret_value"
        )

        # Custom resource for getting prefix list ID
        get_prefix_id_function = SolutionsPythonFunction(
            self,
            "GetPrefixIdFunction",
            globals.CUSTOM_RESOURCES_PATH / "prefix_id_lambda" / "get_prefix_id.py",
            "event_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            description="Lambda function for getting prefix list ID",
            timeout=Duration.minutes(1),
            memory_size=256,
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[
                PowertoolsLayer.get_or_create(self),
                SolutionsLayer.get_or_create(self),
            ],
        )

        get_prefix_id_function.add_environment(
            "SOLUTION_ID", self.node.try_get_context("SOLUTION_ID")
        )
        get_prefix_id_function.add_environment(
            "SOLUTION_VERSION", self.node.try_get_context("SOLUTION_VERSION")
        )

        get_prefix_id_custom_resource = CustomResource(
            self,
            "GetPrefixIdCr",
            service_token=get_prefix_id_function.function_arn,
            properties={},
        )

        get_prefix_id_function_policy = iam.Policy(
            self,
            "GetPrefixIdFunctionPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["ec2:DescribeManagedPrefixLists"], resources=["*"]
                )
            ],
        )
        get_prefix_id_function.role.attach_inline_policy(get_prefix_id_function_policy)

        get_prefix_id_function.node.add_dependency(get_prefix_id_function_policy)

        get_prefix_id_custom_resource.node.add_dependency(get_prefix_id_function)

        prefix_list_id = get_prefix_id_custom_resource.get_att_string("prefix_list_id")

        #  Custom resource creating for Waf Web Acl
        waf_web_acl_function_waf_policy = iam.Policy(
            self,
            "WafWebAclFunctionWafPolicy",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "wafv2:CreateWebACL",
                        "wafv2:DeleteWebACL",
                        "wafv2:UpdateWebACL",
                    ],
                    resources=[
                        f"arn:aws:wafv2:us-east-1:{Aws.ACCOUNT_ID}:global/webacl/PrebidWaf-*",
                        f"arn:aws:wafv2:us-east-1:{Aws.ACCOUNT_ID}:global/managedruleset/*/*",
                    ],
                )
            ],
        )

        create_waf_web_acl_function = SolutionsPythonFunction(
            self,
            "CreateWafWebAclFunction",
            globals.CUSTOM_RESOURCES_PATH
            / "waf_webacl_lambda"
            / "create_waf_webacl.py",
            "event_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            description="Lambda function for creating Waf Web Acl",
            timeout=Duration.minutes(1),
            memory_size=256,
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[
                PowertoolsLayer.get_or_create(self),
                SolutionsLayer.get_or_create(self),
            ],
        )
        create_waf_web_acl_function.add_environment(
            "SOLUTION_ID", self.node.try_get_context("SOLUTION_ID")
        )
        create_waf_web_acl_function.add_environment(
            "SOLUTION_VERSION", self.node.try_get_context("SOLUTION_VERSION")
        )

        create_waf_web_acl_custom_resource = CustomResource(
            self,
            "WafWebAclCr",
            service_token=create_waf_web_acl_function.function_arn,
            properties={},
        )

        create_waf_web_acl_function.node.add_dependency(waf_web_acl_function_waf_policy)
        create_waf_web_acl_function.role.attach_inline_policy(
            waf_web_acl_function_waf_policy
        )

        waf_webacl_arn = create_waf_web_acl_custom_resource.get_att_string("webacl_arn")
        waf_webacl_name = create_waf_web_acl_custom_resource.get_att_string(
            "webacl_name"
        )
        waf_webacl_id = create_waf_web_acl_custom_resource.get_att_string("webacl_id")
        waf_webacl_locktoken = create_waf_web_acl_custom_resource.get_att_string(
            "webacl_locktoken"
        )

        # Create VPC for Prebid containers
        prebid_vpc = ec2.Vpc(
            self,
            "PrebidVpc",
            ip_addresses=ec2.IpAddresses.cidr(globals.VPC_CIDR),
            max_azs=globals.MAX_AZS,
            nat_gateways=globals.NAT_GATEWAYS,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PUBLIC,
                    name=globals.PUB_SUBNET_NAME,
                    cidr_mask=globals.CIDR_MASK,
                ),
                ec2.SubnetConfiguration(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    name=globals.PVT_SUBNET_NAME,
                    cidr_mask=globals.CIDR_MASK,
                ),
            ],
        )

        # Get Vpc private subnets
        prebid_task_subnets = [
            ec2.Subnet.from_subnet_id(self, f"TaskSubnet{i}", subnet_id)
            for (i, subnet_id) in enumerate(
                prebid_vpc.select_subnets(
                    subnet_group_name=globals.PVT_SUBNET_NAME
                ).subnet_ids
            )
        ]

        # Define EFS file system
        prebid_fs = efs.FileSystem(
            self,
            "Prebid-fs",
            vpc=prebid_vpc,
            performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_7_DAYS,
            vpc_subnets=ec2.SubnetSelection(subnet_group_name=globals.PVT_SUBNET_NAME),
            removal_policy=RemovalPolicy.DESTROY,
            encrypted=True,
        )

        prebid_fs_access_point = efs.AccessPoint(
            self,
            "Prebid-fs-access-point",
            file_system=prebid_fs,
            path="/logging",
            create_acl=efs.Acl(owner_uid="1001", owner_gid="1001", permissions="770"),
            posix_user=efs.PosixUser(uid="1001", gid="1001"),
        )

        # Create Task Definition
        prebid_task_definition = ecs.FargateTaskDefinition(
            self,
            "PrebidTaskDef",
            cpu=globals.VCPU,
            memory_limit_mib=globals.MEMORY_LIMIT_MIB,
        )

        # Add EFS volume to task definition
        prebid_task_definition.add_volume(
            name=globals.EFS_VOLUME_NAME,
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=prebid_fs.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    access_point_id=prebid_fs_access_point.access_point_id,
                    iam="ENABLED",
                ),
            ),
        )

        # Public ECR IAM policy to task definition
        prebid_task_definition.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr-public:GetAuthorizationToken",
                    "sts:GetServiceBearerToken",
                    "ecr-public:BatchCheckLayerAvailability",
                    "ecr-public:GetRepositoryPolicy",
                    "ecr-public:DescribeRepositories",
                    "ecr-public:DescribeRegistries",
                    "ecr-public:DescribeImages",
                    "ecr-public:DescribeImageTags",
                    "ecr-public:GetRepositoryCatalogData",
                    "ecr-public:GetRegistryCatalogData",
                ],
                resources=["*"],
            )
        )

        image_ecs_obj = None
        if ECR_REGISTRY is None:
            logger.info("Prepare ECS container image from image asset.")

            docker_build_location = "../../deployment/ecr/prebid-server"
            if os.getcwd().split("/")[-1] == "source":
                docker_build_location = "../deployment/ecr/prebid-server"
            elif os.getcwd().split("/")[-1] == "deployment":
                docker_build_location = "ecr/prebid-server"

            asset = DockerImageAsset(
                self,
                ECR_REPO_NAME,
                directory=docker_build_location,
                platform=Platform.LINUX_AMD64,
            )

            image_ecs_obj = ecs.ContainerImage.from_docker_image_asset(asset)
        else:
            logger.info("Prepare ECS container image from registry.")
            image_ecs_obj = ecs.ContainerImage.from_registry(ECR_REGISTRY)

        # Add Container to Task Definition
        prebid_container = prebid_task_definition.add_container(
            "Prebid-Container",
            image=image_ecs_obj,
            port_mappings=[ecs.PortMapping(container_port=globals.CONTAINER_PORT)],
            logging=ecs.AwsLogDriver(
                stream_prefix="Prebid-Server", mode=ecs.AwsLogDriverMode.NON_BLOCKING
            ),
            environment={
                "AMT_ADAPTER_ENABLED": "false",
                "ECS_ENABLE_SPOT_INSTANCE_DRAINING": "true",
            },
        )

        # Add mount points to container
        prebid_container.add_mount_points(
            ecs.MountPoint(
                container_path=globals.EFS_MOUNT_PATH,
                source_volume=globals.EFS_VOLUME_NAME,
                read_only=False,
            )
        )

        prebid_task_definition.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "elasticfilesystem:ClientRootAccess",
                    "elasticfilesystem:ClientWrite",
                    "elasticfilesystem:ClientMount",
                    "elasticfilesystem:DescribeMountTargets",
                ],
                resources=[
                    f"arn:aws:elasticfilesystem:{Aws.REGION}:{Aws.ACCOUNT_ID}:file-system/{prebid_fs.file_system_id}"
                ],
            )
        )

        prebid_task_definition.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=["ec2:DescribeAvailabilityZones"], resources=["*"]
            )
        )

        # ALB security group
        alb_sec_group = ec2.SecurityGroup(
            self, "Prebid-ALB-security-group", vpc=prebid_vpc
        )

        alb_sec_group.add_ingress_rule(
            peer=ec2.Peer.prefix_list(prefix_list_id),
            connection=ec2.Port.tcp(80),
            description="Allow ingress only from CloudFront",
        )

        alb_sec_group.node.add_dependency(get_prefix_id_custom_resource)

        # Create Application Load Balancer
        prebid_alb = elbv2.ApplicationLoadBalancer(
            self,
            "Prebid-ALB",
            vpc=prebid_vpc,
            internet_facing=True,
            security_group=alb_sec_group,
        )

        # Create ECS Cluster
        prebid_cluster = ecs.Cluster(
            self, "PrebidCluster", vpc=prebid_vpc, container_insights=True
        )

        # ALB-Fargate service pattern
        alb_fargate_service_pattern = (
            ecs_patterns.ApplicationLoadBalancedFargateService(
                self,
                "PrebidFargateService",
                cluster=prebid_cluster,
                task_definition=prebid_task_definition,
                load_balancer=prebid_alb,
                public_load_balancer=True,
                open_listener=False,
                task_subnets=ec2.SubnetSelection(subnets=prebid_task_subnets),
                capacity_provider_strategies=[
                    ecs.CapacityProviderStrategy(
                        capacity_provider="FARGATE",
                        weight=globals.FARGATE_RESERVED_WEIGHT,
                    ),
                    ecs.CapacityProviderStrategy(
                        capacity_provider="FARGATE_SPOT",
                        weight=globals.FARGATE_SPOT_WEIGHT,
                    ),
                ],
            )
        )

        # Allow traffic to/from EFS
        alb_fargate_service_pattern.service.connections.allow_from(
            prebid_fs, ec2.Port.tcp(globals.EFS_PORT)
        )
        alb_fargate_service_pattern.service.connections.allow_to(
            prebid_fs, ec2.Port.tcp(globals.EFS_PORT)
        )

        # Add health check
        alb_fargate_service_pattern.target_group.configure_health_check(
            path=globals.HEALTH_ENDPOINT,
            interval=Duration.seconds(globals.HEALTH_CHECK_INTERVAL_SECS),
            timeout=Duration.seconds(globals.HEALTH_CHECK_TIMEOUT_SECS),
        )

        # Auto scaling groups
        scalable_target = alb_fargate_service_pattern.service.auto_scale_task_count(
            min_capacity=globals.AUTOSCALE_TASK_COUNT_MIN,
            max_capacity=globals.AUTOSCALE_TASK_COUNT_MAX,
        )

        scalable_target.scale_on_cpu_utilization(
            "FargateServiceCpuScaling",
            target_utilization_percent=globals.CPU_TARGET_UTILIZATION_PCT,
        )

        scalable_target.scale_on_memory_utilization(
            "FargateServiceMemoryScaling",
            target_utilization_percent=globals.MEMORY_TARGET_UTILIZATION_PCT,
        )

        scalable_target.scale_on_request_count(
            "FargateServiceRequestCountScaling",
            requests_per_target=globals.REQUESTS_PER_TARGET,
            target_group=alb_fargate_service_pattern.target_group,
        )

        # Create a reference to a managed CloudFront Response Headers Policy
        response_headers_policy = (
            cloudfront.ResponseHeadersPolicy.from_response_headers_policy_id(
                self,
                "CloudFrontResponseHeadersPolicy",
                globals.RESPONSE_HEADERS_POLICY_ID,
            )
        )

        # Define the single ALB origin
        origin = cloudfront_origins.LoadBalancerV2Origin(
            alb_fargate_service_pattern.load_balancer,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
            custom_headers={globals.X_SECRET_HEADER_NAME: x_header_secret_value},
        )

        # define the default cache behavior
        default_behavior = cloudfront.BehaviorOptions(
            origin=origin,
            allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
            origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
            cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
            response_headers_policy=response_headers_policy,
        )

        # create s3 bucket for cloudfront distribution access logs
        cloudfront_access_logs_bucket_key = kms.Key(
            self,
            id="CloudFrontAccessLogsBucketKey",
            description="CloudFront Access Logging Bucket Key",
            enable_key_rotation=True,
            pending_window=Duration.days(30),
            removal_policy=RemovalPolicy.RETAIN,
        )
        kms_bucket_policy = iam.PolicyStatement(
            principals=[iam.ServicePrincipal("delivery.logs.amazonaws.com")],
            effect=iam.Effect.ALLOW,
            actions=["kms:GenerateDataKey*", "kms:Decrypt"],
            resources=["*"],
            conditions={
                "StringEquals": {
                    "aws:SourceAccount": [Aws.ACCOUNT_ID],
                }
            },
        )
        cloudfront_access_logs_bucket_key.add_to_resource_policy(kms_bucket_policy)

        cloudfront_access_logs_bucket = s3.Bucket(
            self,
            id="CloudFrontAccessLogsBucket",
            object_ownership=s3.ObjectOwnership.OBJECT_WRITER,
            encryption_key=cloudfront_access_logs_bucket_key,
            access_control=s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
            enforce_ssl=True,
            object_lock_enabled=True,
        )

        # create the cloudfront distribution
        prebid_cloudfront_distribution = cloudfront.Distribution(
            self,
            "PrebidCloudFrontDist",
            comment="Prebid Server Deployment on AWS",
            default_behavior=default_behavior,
            web_acl_id=waf_webacl_arn,
            enable_logging=True,
            log_bucket=cloudfront_access_logs_bucket,
        )
        prebid_cloudfront_distribution.node.add_dependency(
            header_secret_gen_custom_resource
        )

        # Custom resource for deleting Waf Web Acl
        waf_web_acl_function_cloudfront_policy = iam.Policy(
            self,
            "WafWebAclFunctionCloudFrontPolicy",
            statements=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "cloudfront:GetDistribution",
                        "cloudfront:GetDistributionConfig",
                        "cloudfront:ListDistributions",
                        "cloudfront:ListDistributionsByWebACLId",
                        "cloudfront:UpdateDistribution",
                    ],
                    resources=[
                        f"arn:aws:cloudfront::{Aws.ACCOUNT_ID}:distribution/{prebid_cloudfront_distribution.distribution_id}"
                    ],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "cloudwatch:ListMetrics",
                        "cloudwatch:GetMetricStatistics",
                        "ec2:DescribeRegions",
                    ],
                    resources=["*"],
                ),
            ],
        )
        create_waf_web_acl_function.role.attach_inline_policy(
            waf_web_acl_function_cloudfront_policy
        )

        del_waf_web_acl_function = SolutionsPythonFunction(
            self,
            "DelWafWebAclFunction",
            globals.CUSTOM_RESOURCES_PATH
            / "waf_webacl_lambda"
            / "delete_waf_webacl.py",
            "event_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            description="Lambda function for deleting Waf Web Acl",
            timeout=Duration.minutes(1),
            memory_size=256,
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[
                PowertoolsLayer.get_or_create(self),
                SolutionsLayer.get_or_create(self),
            ],
        )
        del_waf_web_acl_function.add_environment(
            "SOLUTION_ID", self.node.try_get_context("SOLUTION_ID")
        )
        del_waf_web_acl_function.add_environment(
            "SOLUTION_VERSION", self.node.try_get_context("SOLUTION_VERSION")
        )
        del_waf_web_acl_function.node.add_dependency(waf_web_acl_function_waf_policy)
        del_waf_web_acl_function.node.add_dependency(
            waf_web_acl_function_cloudfront_policy
        )
        del_waf_web_acl_function.role.attach_inline_policy(
            waf_web_acl_function_waf_policy
        )
        del_waf_web_acl_function.role.attach_inline_policy(
            waf_web_acl_function_cloudfront_policy
        )

        CustomResource(
            self,
            "DeleteWafWebAclCr",
            service_token=del_waf_web_acl_function.function_arn,
            properties={
                "CF_DISTRIBUTION_ID": prebid_cloudfront_distribution.distribution_id,
                "WAF_WEBACL_NAME": waf_webacl_name,
                "WAF_WEBACL_ID": waf_webacl_id,
                "WAF_WEBACL_LOCKTOKEN": waf_webacl_locktoken,
            },
        )

        # Set up ALB Listener Rule
        listener = alb_fargate_service_pattern.load_balancer.listeners[0]
        listener.add_action(
            "ListenerAction",
            action=elbv2.ListenerAction.fixed_response(
                status_code=401, content_type="text/plain", message_body="Unauthorized"
            ),
        )

        elbv2.ApplicationListenerRule(
            self,
            "PrebidListenerRule",
            listener=listener,
            priority=1,
            conditions=[
                elbv2.ListenerCondition.http_header(
                    globals.X_SECRET_HEADER_NAME, [x_header_secret_value]
                )
            ],
            action=elbv2.ListenerAction.forward(
                [alb_fargate_service_pattern.target_group]
            ),
        )

        # Create artifacts resources for storing solution files
        artifacts_construct = ArtifactsManager(self, "Artifacts")

        # Create DataSync resources for monitoring tasks in CloudWatch
        datasync_monitor = DataSyncMonitoring(self, "DataSyncMonitor")

        # Create DataSync tasks for moving logs and metrics from EFS to S3
        datasync_metrics = DataSyncTask(
            self,
            "DataSyncMetrics",
            vpc=prebid_vpc,
            efs_filesystem=prebid_fs,
            efs_ap=prebid_fs_access_point,
            efs_path=globals.EFS_METRICS,
            filter_pattern="*/prebid-metrics.log",
            task_schedule=globals.DATASYNC_METRICS_SCHEDULE,
            report_bucket=artifacts_construct.bucket,
            log_group=datasync_monitor.log_group,
        )

        datasync_metrics.node.add_dependency(artifacts_construct.bucket)
        datasync_metrics.node.add_dependency(datasync_monitor.log_group)

        datasync_logs = DataSyncTask(
            self,
            "DataSyncLogs",
            vpc=prebid_vpc,
            efs_filesystem=prebid_fs,
            efs_ap=prebid_fs_access_point,
            efs_path="logs",
            filter_pattern="*/prebid-server.log",
            task_schedule=globals.DATASYNC_LOGS_SCHEDULE,
            report_bucket=artifacts_construct.bucket,
            log_group=datasync_monitor.log_group,
        )

        datasync_logs.node.add_dependency(artifacts_construct.bucket)
        datasync_logs.node.add_dependency(datasync_monitor.log_group)

        # Set lifecycle policy for removing datasync reports
        artifacts_construct.bucket.add_lifecycle_rule(
            expiration=Duration.days(globals.DATASYNC_REPORT_LIFECYCLE_DAYS),
            prefix="datasync",
        )

        # Create resources for removing transferred logs and metrics from EFS
        efs_cleanup = EfsCleanup(
            self,
            "EfsCleanup",
            vpc=prebid_vpc,
            efs_ap=prebid_fs_access_point,
            efs_filesystem=prebid_fs,
            report_bucket=artifacts_construct.bucket,
            datasync_tasks={
                globals.EFS_METRICS: datasync_metrics.task,
                globals.EFS_LOGS: datasync_logs.task,
            },
            fargate_cluster_arn=alb_fargate_service_pattern.cluster.cluster_arn,
        )

        # Create Glue resources for ETL of metrics
        glue_etl = GlueEtl(
            self,
            "MetricsEtl",
            artifacts_construct=artifacts_construct,
            script_file_name="metrics_glue_script.py",
            source_bucket=datasync_metrics.bucket,
            datasync_task=datasync_metrics.task,
        )

        # Create datasync-s3 layer used by efs_cleanup and glue_trigger lambdas
        datasync_s3_layer = LayerVersion(
            self,
            "DataSyncS3Layer",
            code=Code.from_asset(
                path=os.path.join(
                    f"{Path(__file__).parents[1]}",
                    "aws_lambda_layers/datasync_s3_layer/",
                )
            ),
            layer_version_name=f"{Aws.STACK_NAME}-datasync-s3-layer",
            compatible_runtimes=[Runtime.PYTHON_3_11],
        )
        glue_etl.lambda_function.add_layers(datasync_s3_layer)
        efs_cleanup.efs_file_del_lambda_function.add_layers(datasync_s3_layer)

        # Create a VPC S3 endpoint to prevent private resources from traversing the public internet when accessing S3
        prebid_s3_endpoint = prebid_vpc.add_gateway_endpoint(
            "s3_gateway_endpoint", service=ec2.GatewayVpcEndpointAwsService.S3
        )
        # Allow access to aws-managed public bucket for ECS to pull Docker image assets:
        # https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html#ecr-minimum-s3-perms
        prebid_s3_endpoint.add_to_policy(
            iam.PolicyStatement(
                principals=[iam.AnyPrincipal()],  # NOSONAR - required for operation
                actions=["s3:GetObject"],
                resources=[f"arn:aws:s3:::prod-{Aws.REGION}-starport-layer-bucket/*"],
            )
        )
        # Allow access to artifacts bucket for EFS Cleanup Lambda to read DataSync reports
        prebid_s3_endpoint.add_to_policy(
            iam.PolicyStatement(
                principals=[iam.AnyPrincipal()],  # NOSONAR - required for operation
                actions=["s3:GetObject", "s3:ListBucket"],
                resources=[
                    artifacts_construct.bucket.bucket_arn,
                    f"{artifacts_construct.bucket.bucket_arn}/*",
                ],
                conditions={
                    "StringEquals": {globals.RESOURCE_NAMESPACE: Aws.ACCOUNT_ID}
                },
            )
        )

        # Operational Metrics
        OperationalMetricsConstruct(
            self,
            "operational-metrics",
        )

        # CloudWatch Metrics
        CloudwatchMetricsConstruct(
            self,
            "cloudwatch-metrics",
            cloud_front_id=prebid_cloudfront_distribution.distribution_id,
            public_subnets=[
                public_subnet.subnet_id for public_subnet in prebid_vpc.public_subnets
            ],
            load_balancer_full_name=prebid_alb.load_balancer_full_name,
        )

        # CloudWatch Alarms
        CloudwatchAlarms(
            self,
            "CloudwatchAlarms",
            application_load_balancer=prebid_alb,
            efs_file_system=prebid_fs,
            vpc=prebid_vpc,
            cloudfront_distribution=prebid_cloudfront_distribution,
            waf_webacl_name=waf_webacl_name,
            glue_job_name=glue_etl.GLUE_JOB_NAME,
        )

        CfnOutput(
            self,
            "Prebid-CloudFrontDistributionEndpoint",
            value=prebid_cloudfront_distribution.domain_name,
        )
        CfnOutput(self, "Prebid-EFSId", value=prebid_fs.file_system_id)
        CfnOutput(
            self, "Prebid-CloudFrontHeaderSecretValue", value=x_header_secret_value
        )
        CfnOutput(self, "Prebid-WAF-WebACL", value=waf_webacl_name)

        # Cloud Trail Logging
        cloudtrail_logging_s3_buckets = [
            artifacts_construct.bucket,
            datasync_metrics.bucket,
            datasync_logs.bucket,
            glue_etl.output_bucket,
        ]

        cloudtrail_logging_lambda_functions = [
            header_secret_gen_function,
            get_prefix_id_function,
            create_waf_web_acl_function,
            del_waf_web_acl_function,
            artifacts_construct.upload_artifacts_function,
            efs_cleanup.efs_file_del_lambda_function,
            efs_cleanup.del_vpc_eni_function,
            efs_cleanup.container_stop_lambda_function,
            glue_etl.lambda_function,
        ]

        cloud_trail_construct = CloudTrailConstruct(
            self,
            "CloudtrailConstruct",
            s3_buckets=cloudtrail_logging_s3_buckets,
            lambda_functions=cloudtrail_logging_lambda_functions,
        )

        # add dependecies on cloudtrail_logging_lambda_functions
        for lambda_function in cloudtrail_logging_lambda_functions:
            cloud_trail_construct.node.add_dependency(lambda_function)

        # add dependecies on cloudtrail_logging_s3_buckets
        for bucket in cloudtrail_logging_s3_buckets:
            cloud_trail_construct.node.add_dependency(bucket)

        # Construct to create custom resource to enable access logging for ALB
        AlbAccessLogsConstruct(
            self, "ALBAccessLogsConstruct", alb_arn=prebid_alb.load_balancer_arn
        )
