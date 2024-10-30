# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


import os
from pathlib import Path

from aws_cdk import CfnCondition, Fn
from aws_cdk import Aws, CfnParameter
from aws_cdk import aws_ecs as ecs
from aws_cdk.aws_lambda import LayerVersion, Code, Runtime
from constructs import Construct

from aws_solutions.cdk.stack import SolutionStack

from .prebid_datasync_constructs import DataSyncMonitoring
from .prebid_artifacts_constructs import ArtifactsManager
from .operational_metrics_construct import OperationalMetricsConstruct
from .cloudfront_entry_deployment import CloudFrontEntryDeployment
from .alb_entry_deployment import ALBEntryDeployment
from .vpc_construct import VpcConstruct
from .container_image_construct import ContainerImageConstruct
from .prebid_glue_constructs import GlueEtl
from .cloudtrail_construct import CloudTrailConstruct


class PrebidServerStack(SolutionStack):
    name = "prebid-server-deployment-on-aws"
    description = "Prebid Server Deployment on AWS"
    template_filename = "prebid-server-deployment-on-aws.template"

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.synthesizer.bind(self)

        deploy_cloudfront_and_waf_param = CfnParameter(
            self,
            id="InstallCloudFrontAndWAF",
            description="Yes - Use the CloudFront and Web Application Firewall to deliver your content. \n No - Skip CloudFront and WAF deployment and use your own content delivery network instead",
            type="String",
            allowed_values=["Yes", "No"],
            default="Yes"
        )

        ssl_certificate_param = CfnParameter(
            self,
            id="SSLCertificateARN",
            description="The ARN of an SSL certificate in AWS Certificate Manager associated with a domain name. This field is only required if InstallCloudFrontAndWAF is set to \"No\".",
            type="String",
            default=""
        )
        self.solutions_template_options.add_parameter(deploy_cloudfront_and_waf_param, label="",
                                                      group="Content Delivery Network (CDN) Settings")
        self.solutions_template_options.add_parameter(ssl_certificate_param, label="",
                                                      group="Content Delivery Network (CDN) Settings")

        deploy_cloudfront_and_waf_condition = CfnCondition(
            self,
            id="DeployCloudFrontWafCondition",
            expression=Fn.condition_equals(deploy_cloudfront_and_waf_param.value_as_string, "Yes")
        )

        deploy_alb_https_condition = CfnCondition(
            self,
            id="DeployALBHttpsCondition",
            expression=Fn.condition_equals(deploy_cloudfront_and_waf_param.value_as_string, "No")
        )

        container_image_construct = ContainerImageConstruct(self, "ContainerImage", self.solutions_template_options)

        # Create artifacts resources for storing solution files
        artifacts_construct = ArtifactsManager(self, "Artifacts")

        vpc_construct = VpcConstruct(self, "VPC", artifacts_construct.bucket,
                                     container_image_construct.docker_configs_manager_bucket)

        # Create ECS Cluster
        prebid_cluster = ecs.Cluster(
            self, "PrebidCluster", vpc=vpc_construct.prebid_vpc, container_insights=True
        )

        # Create DataSync resources for monitoring tasks in CloudWatch
        datasync_monitor = DataSyncMonitoring(self, "DataSyncMonitor")
        # Suppress cfn_guard rule for CloudWatch log encryption since they are
        # encrypted by default.
        log_group_l1_construct = datasync_monitor.log_group.node.find_child(id="Resource")
        log_group_l1_construct.add_metadata(
            "guard", {
                'SuppressedRules': ['CLOUDWATCH_LOG_GROUP_ENCRYPTED']
            }
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

        # Operational Metrics
        OperationalMetricsConstruct(self, "operational-metrics")

        # Create Glue resources for ETL of metrics
        glue_etl = GlueEtl(
            self,
            "MetricsEtl",
            artifacts_construct=artifacts_construct,
            script_file_name="metrics_glue_script.py",
        )
        glue_etl.lambda_function.add_layers(datasync_s3_layer)

        # Cloud Trail Logging
        cloudtrail_logging_s3_buckets = [artifacts_construct.bucket, glue_etl.source_bucket, glue_etl.output_bucket, ]
        CloudTrailConstruct(
            self,
            "CloudtrailConstruct",
            s3_buckets=cloudtrail_logging_s3_buckets,
        )

        # Deploy CloudFrontEntryDeployment construct when the user selects the option to use CloudFront as their content delivery network (CDN).
        # In this case, WAF resources are deployed along with CloudFront.
        CloudFrontEntryDeployment(
            self,
            "CloudFrontEntryDeployment",
            deploy_cloudfront_and_waf_condition,
            artifacts_construct,
            datasync_monitor,
            vpc_construct,
            container_image_construct,
            datasync_s3_layer,
            prebid_cluster,
            glue_etl,
        )

        # Deploy this construct when the user wants to use their own CDN.
        # In this case, CloudFront and WAF are excluded from the stack deployment.
        ALBEntryDeployment(
            self,
            "ALBEntryDeployment",
            deploy_alb_https_condition,
            ssl_certificate_param,
            artifacts_construct,
            datasync_monitor,
            vpc_construct,
            container_image_construct,
            prebid_cluster,
            datasync_s3_layer,
            glue_etl,
        )
