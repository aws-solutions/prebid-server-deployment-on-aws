# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from aws_cdk import (
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
)
from aws_cdk import Aspects, CfnOutput
from .condition_aspect import ConditionAspect
from constructs import Construct
import prebid_server.stack_constants as globals
from .prebid_datasync_constructs import EfsCleanup, DataSyncTask
from .alb_access_logs_construct import AlbAccessLogsConstruct
from .efs_construct import EfsConstruct
from .ecs_task_construct import ECSTaskConstruct
from .ecs_service_construct import ECSServiceConstruct
from .cloudwatch_alarms_construct import CloudwatchAlarms
from .cloudwatch_metrics_construct import CloudwatchMetricsConstruct


class ALBEntryDeployment(Construct):
    def __init__(
            self,
            scope,
            id,
            deploy_alb_https_condition,
            ssl_certificate_param,
            artifacts_construct,
            datasync_monitor,
            vpc_construct,
            container_image_construct,
            prebid_cluster,
            datasync_s3_layer,
            glue_etl,
    ) -> None:
        """
        This construct creates resources needed for the user to use a different CDN.
        The stack utilizes an SSL certificate provided by the user to establish an HTTPS listener in an Application Load Balancer.
        """
        super().__init__(scope, id)

        # Apply condition to resources in this construct
        Aspects.of(self).add(ConditionAspect(self, "Condition", deploy_alb_https_condition))

        prebid_vpc = vpc_construct.prebid_vpc
        prebid_task_subnets = vpc_construct.prebid_task_subnets
        image_ecs_obj = container_image_construct.image_ecs_obj
        docker_configs_manager_bucket = container_image_construct.docker_configs_manager_bucket

        efs_construct = EfsConstruct(self, "Efs", prebid_vpc)

        ecs_task_construct = ECSTaskConstruct(self, "ECSTask", image_ecs_obj, efs_construct.prebid_fs,
                                              efs_construct.prebid_fs_access_point, docker_configs_manager_bucket)

        # ALB security group
        alb_sec_group = ec2.SecurityGroup(self, "Prebid-ALB-security-group", vpc=prebid_vpc) # NOSONAR
        # These ingress rules are for ALB HTTPS listener only.
        alb_sec_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow ingress from any IPv4 address",
        )
        alb_sec_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv6(),
            connection=ec2.Port.tcp(80),
            description="Allow ingress from any IPv6 address",
        )
        # Suppress cfn_guard warning about open egress in the ALB security
        # group because Prebid Server containers require open egress in order
        # to connect to demand partners.
        #
        # The cfn_guard warning about open ingress and non-32 rule is also
        # suppressed because Prebid Server containers require open ingress in
        # order to connect to clients through the Internet facing ALB.
        security_group_l1_construct = alb_sec_group.node.find_child(id='Resource')
        security_group_l1_construct.add_metadata("guard", {
            'SuppressedRules': [
                'EC2_SECURITY_GROUP_EGRESS_OPEN_TO_WORLD_RULE',
                'SECURITY_GROUP_EGRESS_ALL_PROTOCOLS_RULE',
                'EC2_SECURITY_GROUP_INGRESS_OPEN_TO_WORLD_RULE',
                'SECURITY_GROUP_INGRESS_CIDR_NON_32_RULE'
            ]})


        # Create Application Load Balancer
        prebid_alb = elbv2.ApplicationLoadBalancer(
            self,
            "Prebid-ALB",
            vpc=prebid_vpc,
            internet_facing=True,
            security_group=alb_sec_group,
        )
        CfnOutput(self, "Prebid-ALBDNSName", key="PrebidALBDNSName", value=prebid_alb.load_balancer_dns_name,
                  condition=deploy_alb_https_condition)

        # Suppress cfn_guard warning about access logs in the ALB because
        # access logs are added to the ALB in alb_access_logs_construct.py
        prebid_alb_l1_construct = prebid_alb.node.find_child(id="Resource")
        prebid_alb_l1_construct.add_metadata("guard", {'SuppressedRules': ['ELBV2_ACCESS_LOGGING_RULE']})

        ecs_service_construct = ECSServiceConstruct(self, "ECSService", prebid_vpc,
                                                    prebid_cluster,
                                                    ecs_task_construct.prebid_task_definition,
                                                    prebid_task_subnets,
                                                    ecs_task_construct.prebid_container,
                                                    efs_construct.prebid_fs)

        # Create an HTTPS listener in ALB using an SSL certificate arn specified in a CloudFormation template parameter.
        https_listener = prebid_alb.add_listener("HTTPSListener",
                                                 port=443,
                                                 protocol=elbv2.ApplicationProtocol.HTTPS,
                                                 certificates=[elbv2.ListenerCertificate.from_arn(
                                                     ssl_certificate_param.value_as_string)],
                                                 default_action=elbv2.ListenerAction.forward(
                                                     [ecs_service_construct.alb_target_group]),
                                                 )

        # Suppress cfn_guard warning about an absent SslPolicy. This is an HTTP listener.
        # This listener is only used for HTTP traffic on the VPC between Cloudfront and
        # Prebid Server runtimes.
        https_listener.node.find_child(id='Resource').add_metadata("guard", {
            'SuppressedRules': ['ELBV2_LISTENER_SSL_POLICY_RULE', 'ELBV2_LISTENER_PROTOCOL_RULE']})

        # Setup auto-scaling rule for the Fargate service.
        # Note that this can only be done after the ALB listener rule has been created, this the scaling rule relies on the ALB to route incoming requests to the Fargate service.
        # The order in which resources are created matters here, so be sure to create the ALB listener rule before setting up this auto-scaling rule
        ecs_service_construct.scalable_target.scale_on_request_count(
            "FargateServiceRequestCountScaling",
            requests_per_target=globals.REQUESTS_PER_TARGET,
            target_group=ecs_service_construct.alb_target_group,
        )

        # Create DataSync tasks for moving logs and metrics from EFS to S3
        datasync_metrics = DataSyncTask(
            self,
            "DataSyncMetrics",
            vpc=prebid_vpc,
            efs_filesystem=efs_construct.prebid_fs,
            efs_ap=efs_construct.prebid_fs_access_point,
            efs_path=globals.EFS_METRICS,
            filter_pattern="*/prebid-metrics.log",
            task_schedule=globals.DATASYNC_METRICS_SCHEDULE,
            report_bucket=artifacts_construct.bucket,
            log_group=datasync_monitor.log_group,
            glue_etl_job_trigger=glue_etl.lambda_function,
            glue_etl_s3_location=glue_etl.s3_location,
        )

        datasync_metrics.node.add_dependency(artifacts_construct.bucket)
        datasync_metrics.node.add_dependency(datasync_monitor.log_group)

        # Suppress cfn_guard warning about missing egress rule. Justification:
        # The Datasync construct creates a security group without an efgress rule.
        # Security groups without an egress rule allow all outbound traffic by default.
        # Datasync lies within our trust domain. We trust outbound traffic from that service.
        for child in datasync_metrics.node.find_all():
            if isinstance(child, ec2.SecurityGroup):
                security_group_l1_construct = child.node.find_child(id="Resource")
                security_group_l1_construct.add_metadata("guard",
                                                         {'SuppressedRules': ['SECURITY_GROUP_MISSING_EGRESS_RULE']})

        # Create resources for removing transferred logs and metrics from EFS
        efs_cleanup = EfsCleanup(
            self,
            "EfsCleanup",
            vpc=prebid_vpc,
            efs_ap=efs_construct.prebid_fs_access_point,
            efs_filesystem=efs_construct.prebid_fs,
            report_bucket=artifacts_construct.bucket,
            datasync_tasks={
                globals.EFS_METRICS: datasync_metrics.task,
            },
            fargate_cluster_arn=prebid_cluster.cluster_arn,
        )
        efs_cleanup.efs_file_del_lambda_function.add_layers(datasync_s3_layer)

        CfnOutput(self, "Prebid-EFSId", value=efs_construct.prebid_fs.file_system_id,
                  condition=deploy_alb_https_condition)

        # CloudWatch Alarms
        CloudwatchAlarms(
            self,
            "CloudwatchAlarms",
            application_load_balancer=prebid_alb,
            efs_file_system=efs_construct.prebid_fs,
            vpc=prebid_vpc,
            glue_job_name=glue_etl.GLUE_JOB_NAME,
        )

        # CloudWatch Metrics
        CloudwatchMetricsConstruct(
            self,
            "cloudwatch-metrics",
            public_subnets=[
                public_subnet.subnet_id for public_subnet in prebid_vpc.public_subnets
            ],
            load_balancer_full_name=prebid_alb.load_balancer_full_name,
        )

        # Construct to create custom resource to enable access logging for ALB
        AlbAccessLogsConstruct(
            self, "ALBAccessLogsConstruct", alb_arn=prebid_alb.load_balancer_arn
        )
