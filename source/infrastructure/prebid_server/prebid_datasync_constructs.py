# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

from aws_cdk import Aws, Duration, CustomResource, RemovalPolicy
from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_datasync as datasync,
    aws_efs as efs,
    aws_s3 as s3,
    aws_lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_kms as kms,
    aws_logs,
)
from aws_cdk.aws_lambda import LayerVersion, Code, Runtime
from constructs import Construct

from aws_lambda_layers.aws_solutions.layer import SolutionsLayer
import prebid_server.stack_constants as globals
from aws_solutions.cdk.aws_lambda.python.function import SolutionsPythonFunction
from aws_solutions.cdk.aws_lambda.layers.aws_lambda_powertools import PowertoolsLayer

DATASYNC_SERVICE_PRINCIPAL = iam.ServicePrincipal("datasync.amazonaws.com")
S3_READ_ACTIONS = ["s3:GetObject", "s3:ListBucket"]
ACCOUNT_ID_CONDITION = {"StringEquals": {globals.RESOURCE_NAMESPACE: [Aws.ACCOUNT_ID]}}

# This policy is required to deploy a VPC Lambda
# https://docs.aws.amazon.com/lambda/latest/dg/configuration-vpc.html#vpc-permissions
VPC_NW_INTERFACE_POLICY_STATEMENT = iam.PolicyStatement(
    actions=[
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface",
    ],
    resources=["*"],  # NOSONAR
    conditions={"StringEquals": {globals.RESOURCE_NAMESPACE: [Aws.ACCOUNT_ID]}},
)


class EfsLocation(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        prebid_vpc: ec2.Vpc,
        efs_filesystem: efs.FileSystem,
        efs_path: str,
        efs_ap: efs.AccessPoint,
    ):
        super().__init__(scope, id)

        self.prebid_vpc = prebid_vpc
        self.efs_filesystem = efs_filesystem
        self.efs_path = efs_path
        self.efs_ap = efs_ap
        self.efs_location = self._create_efs_location()

    def _create_efs_location(self):
        """
        This function creates an EFS Location resource used for DataSync Tasks involving EFS
        """
        # create permissions for DataSync EFS access
        datasync_efs_role = iam.Role(
            self,
            "Role",
            assumed_by=DATASYNC_SERVICE_PRINCIPAL,
        )

        datasync_efs_policy = iam.Policy(
            self,
            "Policy",
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "elasticfilesystem:DescribeMountTargets",
                        "elasticfilesystem:ClientMount",
                        "elasticfilesystem:ClientWrite",
                        "elasticfilesystem:ClientRootAccess",
                    ],
                    resources=[self.efs_filesystem.file_system_arn],
                ),
            ],
        )
        datasync_efs_role.attach_inline_policy(datasync_efs_policy)

        datasync_efs_sec_group = ec2.SecurityGroup(
            self, "SecurityGroup", vpc=self.prebid_vpc
        )
        datasync_efs_sec_group.connections.allow_from(
            self.efs_filesystem, ec2.Port.tcp(globals.EFS_PORT)
        )
        datasync_efs_sec_group.connections.allow_to(
            self.efs_filesystem, ec2.Port.tcp(globals.EFS_PORT)
        )

        # create DataSync EFS location
        subnet_id = self.prebid_vpc.select_subnets(
            subnet_group_name=globals.PVT_SUBNET_NAME
        ).subnet_ids[0]

        datasync_efs_location = datasync.CfnLocationEFS(
            self,
            "Location",
            ec2_config=datasync.CfnLocationEFS.Ec2ConfigProperty(
                security_group_arns=[
                    f"arn:aws:ec2:{Aws.REGION}:{Aws.ACCOUNT_ID}:security-group/{datasync_efs_sec_group.security_group_id}"
                ],
                subnet_arn=f"arn:aws:ec2:{Aws.REGION}:{Aws.ACCOUNT_ID}:subnet/{subnet_id}",
            ),
            access_point_arn=self.efs_ap.access_point_arn,
            in_transit_encryption="TLS1_2",
            efs_filesystem_arn=self.efs_filesystem.file_system_arn,
            file_system_access_role_arn=datasync_efs_role.role_arn,
            subdirectory=self.efs_path,
        )
        datasync_efs_location.node.add_dependency(self.efs_filesystem)

        return datasync_efs_location


class S3Location(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        s3_bucket: s3.Bucket,
    ):
        super().__init__(scope, id)

        self.s3_bucket = s3_bucket
        self.S3_PERMISSIONS = [
            "s3:GetBucketLocation",
            "s3:ListBucketMultipartUploads",
            "s3:AbortMultipartUpload",
            "s3:DeleteObject",
            "s3:ListMultipartUploadParts",
            "s3:GetObjectTagging",
            "s3:PutObjectTagging",
            "s3:PutObject",
        ]
        self.S3_PERMISSIONS.extend(S3_READ_ACTIONS)

        self.s3_location = self._create_s3_location()

    def _create_s3_location(self):
        """
        This function creates an S3 Location resource used for DataSync Tasks involving S3
        """
        # create Datasync role to access S3 bucket
        datasync_s3_role = iam.Role(
            self,
            "Role",
            assumed_by=DATASYNC_SERVICE_PRINCIPAL,
        )
        datasync_s3_policy = iam.Policy(
            self,
            "Policy",
            statements=[
                iam.PolicyStatement(
                    actions=self.S3_PERMISSIONS,
                    resources=[
                        self.s3_bucket.bucket_arn,
                        f"{self.s3_bucket.bucket_arn}/*",
                    ],
                    conditions=ACCOUNT_ID_CONDITION,
                ),
            ],
        )
        datasync_s3_role.attach_inline_policy(datasync_s3_policy)
        self.s3_bucket.encryption_key.grant_encrypt_decrypt(datasync_s3_role)
        datasync_s3_policy.node.add_dependency(self.s3_bucket)

        # Create bucket policy to grant DataSync access
        datasync_bucket_policy_statement = iam.PolicyStatement(
            principals=[iam.ArnPrincipal(datasync_s3_role.role_arn)],
            actions=self.S3_PERMISSIONS,
            resources=[
                self.s3_bucket.bucket_arn,
                f"{self.s3_bucket.bucket_arn}/*",
            ],
            conditions=ACCOUNT_ID_CONDITION,
        )
        bucket_policy = s3.BucketPolicy(
            self,
            "BucketPolicy",
            bucket=self.s3_bucket,
            removal_policy=RemovalPolicy.RETAIN,
        )
        bucket_policy.document.add_statements(datasync_bucket_policy_statement)
        bucket_policy.node.add_dependency(self.s3_bucket)

        # Create DataSync S3 location
        datasync_s3_location = datasync.CfnLocationS3(
            self,
            "Location",
            s3_bucket_arn=self.s3_bucket.bucket_arn,
            s3_config=datasync.CfnLocationS3.S3ConfigProperty(
                bucket_access_role_arn=datasync_s3_role.role_arn
            ),
        )
        datasync_s3_location.node.add_dependency(self.s3_bucket)
        datasync_s3_location.node.add_dependency(bucket_policy)

        return datasync_s3_location


class EfsCleanup(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        efs_ap: efs.AccessPoint,
        efs_filesystem: efs.FileSystem,
        report_bucket: s3.Bucket,
        datasync_tasks: dict[str, datasync.CfnTask],
        fargate_cluster_arn: str,
    ):
        super().__init__(scope, id)

        self.vpc = vpc
        self.efs_ap = efs_ap
        self.efs_filesystem = efs_filesystem
        self.report_bucket = report_bucket
        self.datasync_tasks = datasync_tasks
        self.fargate_cluster_arn = fargate_cluster_arn

        self._resource_prefix = Aws.STACK_NAME
        self._create_lamda_layer()
        self.lambda_security_group = self._create_security_group()
        self.efs_file_del_lambda_function = self._create_efs_file_del_lambda_function()
        self._create_lambda_trigger()
        self.container_stop_lambda_function = (
            self._create_container_stop_logs_lambda_function()
        )
        self._create_container_stop_logs_lambda_trigger()
        self._create_del_vpc_eni_custom_resource()

    def _create_lamda_layer(self):
        self.powertools_layer = PowertoolsLayer.get_or_create(self)
        self.metrics_layer = LayerVersion(
            self,
            "metrics-layer",
            code=Code.from_asset(
                path=os.path.join(
                    f"{Path(__file__).parents[1]}", "aws_lambda_layers/metrics_layer/"
                )
            ),
            layer_version_name=f"{self._resource_prefix}-metrics-layer",
            compatible_runtimes=[Runtime.PYTHON_3_11],
        )

    def _create_security_group(self):
        """
        This function creates a security group needed for the VPC Lambda to access the EFS filesystem
        """
        lambda_security_group = ec2.SecurityGroup(self, "SecurityGroup", vpc=self.vpc)
        lambda_security_group.connections.allow_from(
            self.efs_filesystem, ec2.Port.tcp(globals.EFS_PORT)
        )
        lambda_security_group.connections.allow_to(
            self.efs_filesystem, ec2.Port.tcp(globals.EFS_PORT)
        )

        return lambda_security_group

    def _create_container_stop_logs_lambda_function(self):
        container_lambda_function = SolutionsPythonFunction(
            self,
            "ContainerStopFunction",
            Path(__file__).absolute().parents[0]
            / "efs_cleanup_lambda"
            / "container_stop_logs.py",
            "event_handler",
            security_groups=[self.lambda_security_group],
            vpc=self.vpc,
            filesystem=aws_lambda.FileSystem.from_efs_access_point(
                ap=self.efs_ap,
                mount_path=globals.EFS_MOUNT_PATH,
            ),
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            description="Lambda function for archiving logs on container stopping",
            timeout=Duration.seconds(60),
            memory_size=256,
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[
                PowertoolsLayer.get_or_create(self),
                SolutionsLayer.get_or_create(self),
            ],
            environment={
                "SOLUTION_ID": self.node.try_get_context("SOLUTION_ID"),
                "SOLUTION_VERSION": self.node.try_get_context("SOLUTION_VERSION"),
                "EFS_MOUNT_PATH": globals.EFS_MOUNT_PATH,
                "EFS_METRICS": globals.EFS_METRICS,
                "EFS_LOGS": globals.EFS_LOGS,
                "RESOURCE_PREFIX": Aws.STACK_NAME,
                "METRICS_NAMESPACE": self.node.try_get_context("METRICS_NAMESPACE"),
            },
        )
        self.efs_filesystem.grant_read_write(container_lambda_function.role)
        container_lambda_function_policy = iam.Policy(
            self,
            "ContainerLambdaPolicy",
            statements=[VPC_NW_INTERFACE_POLICY_STATEMENT],
        )
        container_lambda_function.role.attach_inline_policy(
            container_lambda_function_policy
        )

        return container_lambda_function

    def _create_efs_file_del_lambda_function(self):
        """
        This function creates a Lambda function that deletes files from EFS that have been transferred to S3
        """
        lambda_function = SolutionsPythonFunction(
            self,
            "Function",
            Path(__file__).absolute().parents[0]
            / "efs_cleanup_lambda"
            / "delete_efs_files.py",
            "event_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            security_groups=[self.lambda_security_group],
            description="Lambda function for cleaning transferred files from EFS",
            memory_size=256,
            timeout=Duration.minutes(15),
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[
                self.powertools_layer,
                SolutionsLayer.get_or_create(self),
                self.metrics_layer,
            ],
            vpc=self.vpc,
            environment={
                "SOLUTION_ID": self.node.try_get_context("SOLUTION_ID"),
                "SOLUTION_VERSION": self.node.try_get_context("SOLUTION_VERSION"),
                "EFS_MOUNT_PATH": globals.EFS_MOUNT_PATH,
                "LOGS_TASK_ARN": self.datasync_tasks["logs"].attr_task_arn,
                "METRICS_TASK_ARN": self.datasync_tasks["metrics"].attr_task_arn,
                "RESOURCE_PREFIX": Aws.STACK_NAME,
                "METRICS_NAMESPACE": self.node.try_get_context("METRICS_NAMESPACE"),
                "DATASYNC_REPORT_BUCKET": self.report_bucket.bucket_name,
                "AWS_ACCOUNT_ID": Aws.ACCOUNT_ID,
                "EFS_METRICS": globals.EFS_METRICS,
                "EFS_LOGS": globals.EFS_LOGS,
            },
            filesystem=aws_lambda.FileSystem.from_efs_access_point(
                ap=self.efs_ap,
                mount_path=globals.EFS_MOUNT_PATH,
            ),
        )

        # Create cleanup lambda iam policy permissions
        lambda_policy = iam.Policy(
            self,
            "LambdaPolicy",
            statements=[
                VPC_NW_INTERFACE_POLICY_STATEMENT,
                iam.PolicyStatement(
                    actions=[
                        "cloudwatch:PutMetricData",
                    ],
                    resources=[
                        "*"  # NOSONAR
                    ],
                    conditions={
                        "StringEquals": {
                            "cloudwatch:namespace": self.node.try_get_context(
                                "METRICS_NAMESPACE"
                            )
                        }
                    },
                ),
                iam.PolicyStatement(
                    actions=S3_READ_ACTIONS,
                    resources=[
                        self.report_bucket.bucket_arn,
                        f"{self.report_bucket.bucket_arn}/*",
                    ],
                    conditions=ACCOUNT_ID_CONDITION,
                ),
            ],
        )
        lambda_function.role.attach_inline_policy(lambda_policy)
        self.efs_filesystem.grant_read_write(lambda_function.role)
        self.report_bucket.encryption_key.grant_encrypt_decrypt(lambda_function.role)

        return lambda_function

    def _create_lambda_trigger(self):
        """
        This function creates an EventBridge rule that triggers the EFS Cleanup Lambda function when DataSync runs a task successfully
        """
        self.efs_file_del_lambda_function.add_permission(
            id="InvokeLambda",
            principal=iam.ServicePrincipal("events.amazonaws.com"),
            action="lambda:InvokeFunction",
        )
        rule = events.Rule(
            self,
            "EventBridgeRule",
            event_pattern=events.EventPattern(
                source=["aws.datasync"],
                detail_type=["DataSync Task Execution State Change"],
                resources=[""],
                # due to a cdk limitation, this is left empty and replaced with the override below (https://github.com/aws/aws-cdk/issues/28462)
                detail={"State": ["SUCCESS"]},
            ),
        )
        rule.node.default_child.add_property_override(
            "EventPattern.resources",
            [
                {"wildcard": f"{task.attr_task_arn}/execution/*"}
                for _, task in self.datasync_tasks.items()
            ],
        )

        rule.add_target(targets.LambdaFunction(self.efs_file_del_lambda_function))

        for _, task in self.datasync_tasks.items():
            rule.node.add_dependency(task)

    def _create_container_stop_logs_lambda_trigger(self):
        self.container_stop_lambda_function.add_permission(
            id="InvokeLambda",
            principal=iam.ServicePrincipal("events.amazonaws.com"),
            action="lambda:InvokeFunction",
        )

        rule = events.Rule(
            self,
            "ContainerLambdaEventBridgeRule",
            event_pattern=events.EventPattern(
                source=["aws.ecs"],
                detail_type=["ECS Task State Change"],
                detail={
                    "lastStatus": ["STOPPING"],
                    "clusterArn": [self.fargate_cluster_arn],
                },
            ),
        )
        rule.add_target(targets.LambdaFunction(self.container_stop_lambda_function))

    def _create_del_vpc_eni_custom_resource(self):
        """
        This function creates a Custom Resource to delete Lambda service VPC ENIs
        """
        # When placing a Lambda inside a VPC, CloudFormation automatically creates VPC ENIs to communicate
        # with the service. Without this Custom Resource, the stack fails to delete because of a dependent
        # resource on the VPC not tied to the stack.
        custom_resource_role = iam.Role(
            self,
            "CrRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "LambdaCrLoggingPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            resources=[
                                f"arn:{Aws.PARTITION}:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/*"
                            ],
                        )
                    ]
                ),
                "LambdaCrEniPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["ec2:DeleteNetworkInterface"],
                            resources=["*"],
                            conditions={
                                "StringEquals": {"ec2:Vpc": f"{self.vpc.vpc_arn}"}
                            },
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "ec2:DescribeNetworkInterfaces",
                                "ec2:DetachNetworkInterface",
                            ],
                            resources=["*"],
                            conditions={
                                "StringEquals": {
                                    globals.RESOURCE_NAMESPACE: [Aws.ACCOUNT_ID]
                                }
                            },
                        ),
                    ]
                ),
            },
        )

        self.del_vpc_eni_function = SolutionsPythonFunction(
            self,
            "VpcEniFunction",
            globals.CUSTOM_RESOURCES_PATH / "vpc_eni_lambda" / "delete_lambda_eni.py",
            "event_handler",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            role=custom_resource_role,
            description="Lambda function for deleting VPC ENIs for the Lambda service",
            memory_size=256,
            architecture=aws_lambda.Architecture.ARM_64,
            layers=[self.powertools_layer, SolutionsLayer.get_or_create(self)],
            environment={
                "SOLUTION_ID": self.node.try_get_context("SOLUTION_ID"),
                "SOLUTION_VERSION": self.node.try_get_context("SOLUTION_VERSION"),
            },
        )

        del_vpc_eni_custom_resource = CustomResource(
            self,
            "VpcEniCr",
            service_token=self.del_vpc_eni_function.function_arn,
            properties={
                "SECURITY_GROUP_ID": self.lambda_security_group.security_group_id
            },
        )
        self.efs_file_del_lambda_function.node.add_dependency(
            del_vpc_eni_custom_resource
        )
        self.container_stop_lambda_function.node.add_dependency(
            del_vpc_eni_custom_resource
        )


class TaskReport(Construct):
    def __init__(self, scope: Construct, id: str, s3_bucket: s3.Bucket):
        super().__init__(scope, id)

        self.bucket = s3_bucket
        self.bucket_prefix = "datasync"
        self.task_config = self._create_report_config()

    def _create_report_config(self):
        """
        This function creates a DataSync Task Report used by the Metrics ETL Lambda and EFS Cleanup Lambda to retrieve transferred S3 files
        """
        datasync_report_role = iam.Role(
            self, "Role", assumed_by=DATASYNC_SERVICE_PRINCIPAL
        )
        datasync_report_policy = iam.Policy(
            self,
            "Policy",
            statements=[
                iam.PolicyStatement(
                    actions=["s3:PutObject", "s3:ListBucket"],
                    resources=[self.bucket.bucket_arn, f"{self.bucket.bucket_arn}/*"],
                    conditions=ACCOUNT_ID_CONDITION,
                )
            ],
        )
        datasync_report_policy.node.add_dependency(self.bucket)
        datasync_report_role.attach_inline_policy(datasync_report_policy)
        self.bucket.encryption_key.grant_encrypt_decrypt(datasync_report_role)

        task_report_config = datasync.CfnTask.TaskReportConfigProperty(
            destination=datasync.CfnTask.DestinationProperty(
                s3=datasync.CfnTask.S3Property(
                    bucket_access_role_arn=datasync_report_role.role_arn,
                    s3_bucket_arn=self.bucket.bucket_arn,
                    subdirectory=self.bucket_prefix,
                )
            ),
            object_version_ids="NONE",
            output_type="STANDARD",
            report_level="SUCCESSES_AND_ERRORS",
            overrides=datasync.CfnTask.OverridesProperty(
                skipped=datasync.CfnTask.SkippedProperty(report_level="ERRORS_ONLY"),
                transferred=datasync.CfnTask.TransferredProperty(
                    report_level="ERRORS_ONLY"
                ),
            ),
        )

        return task_report_config


class DataSyncTask(Construct):
    """
    This construct creates all resources needed for DataSync to sync files between EFS and S3
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        efs_filesystem: efs.FileSystem,
        efs_ap: efs.AccessPoint,
        efs_path: str,
        filter_pattern: str,
        report_bucket: s3.Bucket,
        task_schedule: str,
        log_group: aws_logs.LogGroup,
    ):
        super().__init__(scope, id)

        self.id = id
        self.vpc = vpc
        self.efs_filesystem = efs_filesystem
        self.efs_ap = efs_ap
        self.efs_path = efs_path
        self.filter_pattern = filter_pattern
        self.report_bucket = report_bucket
        self.task_schedule = task_schedule
        self.log_group = log_group

        # We initiate this class twice. Once for the Logs Task and again for the Metrics Task,
        # creating the following resources for each Task:
        datasync_logs_bucket_key = kms.Key(
            self,
            id="BucketKey",
            description=f"{self.id} Bucket Key",
            enable_key_rotation=True,
            pending_window=Duration.days(30),
            removal_policy=RemovalPolicy.RETAIN,
        )
        kms_bucket_policy = iam.PolicyStatement(
            sid=f"Allow access to {self.id}Bucket",
            principals=[
                iam.ServicePrincipal("s3.amazonaws.com"),
                iam.ServicePrincipal("datasync.amazonaws.com"),
                iam.ServicePrincipal("glue.amazonaws.com"),
            ],
            effect=iam.Effect.ALLOW,
            actions=[
                "kms:Encrypt",
                "kms:Decrypt",
                "kms:ReEncrypt*",
                "kms:GenerateDataKey*",
                "kms:CreateGrant",
                "kms:DescribeKey",
            ],
            resources=["*"],
            conditions={
                "StringEquals": {
                    "aws:SourceAccount": [f"{Aws.ACCOUNT_ID}"],
                }
            },
        )
        datasync_logs_bucket_key.add_to_resource_policy(kms_bucket_policy)

        self.bucket = s3.Bucket(
            self,
            "Bucket",
            object_ownership=s3.ObjectOwnership.OBJECT_WRITER,
            access_control=s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption_key=datasync_logs_bucket_key,
            removal_policy=RemovalPolicy.RETAIN,
            versioned=True,
            enforce_ssl=True,
            object_lock_enabled=True,
        )
        self.bucket.node.add_dependency(datasync_logs_bucket_key)

        self.efs_location = EfsLocation(
            self,
            "EfsLocation",
            prebid_vpc=self.vpc,
            efs_filesystem=self.efs_filesystem,
            efs_path=self.efs_path,
            efs_ap=self.efs_ap,
        )

        self.s3_location = S3Location(self, "S3Location", s3_bucket=self.bucket)
        self.s3_location.node.add_dependency(self.bucket)

        self.task_report = TaskReport(self, "TaskReport", s3_bucket=self.report_bucket)
        self.task_report.node.add_dependency(self.report_bucket)

        self.task = datasync.CfnTask(
            self,
            "Task",
            name=f"{Aws.STACK_NAME}-{self.id}-task",
            destination_location_arn=self.s3_location.s3_location.attr_location_arn,
            source_location_arn=self.efs_location.efs_location.attr_location_arn,
            schedule=datasync.CfnTask.TaskScheduleProperty(
                schedule_expression=self.task_schedule
            ),
            options=datasync.CfnTask.OptionsProperty(
                transfer_mode="CHANGED",
                verify_mode="ONLY_FILES_TRANSFERRED",
                log_level="BASIC",
            ),
            excludes=[
                datasync.CfnTask.FilterRuleProperty(
                    filter_type="SIMPLE_PATTERN", value=self.filter_pattern
                )
            ],
            task_report_config=self.task_report.task_config,
            cloud_watch_log_group_arn=self.log_group.log_group_arn,
        )
        self.task.node.add_dependency(self.log_group)
        self.task.node.add_dependency(self.bucket)
        self.task.node.add_dependency(self.report_bucket)
        self.task.node.add_dependency(self.s3_location)
        self.task.node.add_dependency(self.task_report)


class DataSyncMonitoring(Construct):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)

        self.log_group = self._create_log_group()

    def _create_log_group(self):
        """
        This function creates a Cloudwatch Log Group for the DataSync Tasks
        """
        # DataSync requires a resource policy be created on Cloudwatch Logs that
        # explicitly grants the service access (it does not have permission by default).
        # https://docs.aws.amazon.com/datasync/latest/userguide/monitor-datasync.html#configure-logging
        log_group = aws_logs.LogGroup(self, "LogGroup")
        aws_logs.ResourcePolicy(
            self,
            "ResourcePolicy",
            policy_statements=[
                iam.PolicyStatement(
                    principals=[DATASYNC_SERVICE_PRINCIPAL],
                    actions=["logs:PutLogEvents", "logs:CreateLogStream"],
                    resources=[f"{log_group.log_group_arn}:*"],
                    conditions={
                        "ArnLike": {
                            "aws:SourceArn": [
                                f"arn:aws:datasync:{Aws.REGION}:{Aws.ACCOUNT_ID}:task/*"
                            ]
                        }
                    },
                )
            ],
            resource_policy_name=f"{Aws.STACK_NAME}-DataSyncLogPolicy",
        )

        return log_group
