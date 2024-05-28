# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from aws_cdk import CfnResource
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_efs as efs
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_cloudfront as cloudfront
from constructs import Construct

import prebid_server.stack_constants as globals


class CloudwatchAlarms(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        application_load_balancer: elbv2.ApplicationLoadBalancer,
        efs_file_system: efs.FileSystem,
        vpc: ec2.Vpc,
        cloudfront_distribution: cloudfront.Distribution,
        waf_webacl_name: str,
        glue_job_name: str,
        **kwargs,
    ):
        super().__init__(scope, id, **kwargs)

        self.prebid_alb = application_load_balancer
        self.prebid_fs = efs_file_system
        self.prebid_vpc = vpc
        self.prebid_cloudfront_distribution = cloudfront_distribution
        self.waf_webacl_name = waf_webacl_name
        self.glue_job_name = glue_job_name

        self._create_ecs_alarms()
        self._create_alb_alarms()
        self._create_cloudfront_alarms()
        self._create_efs_alarms()
        self._create_nat_alarms()
        self._create_waf_alarms()
        self._create_glue_alarms()

    @staticmethod
    def threshold_add_10pct(x: int) -> int:
        return x + int(0.1 * x)

    def _create_ecs_alarms(self):
        CfnResource(
            self,
            "ECSUtilizationCPUAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": CloudwatchAlarms.threshold_add_10pct(
                    globals.CPU_TARGET_UTILIZATION_PCT
                ),
                "ComparisonOperator": "GreaterThanOrEqualToThreshold",
                "TreatMissingData": "missing",
                "Metrics": [
                    {
                        "Id": "ecs_cpu_utilization",
                        "Label": "ECS CPU Utilization",
                        "ReturnData": True,
                        "Expression": 'SELECT AVG(CPUUtilization) FROM SCHEMA("AWS/ECS", ClusterName,ServiceName)',
                        "Period": 60,
                    }
                ],
            },
        )

        CfnResource(
            self,
            "ECSUtilizationMemoryAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": CloudwatchAlarms.threshold_add_10pct(
                    globals.MEMORY_TARGET_UTILIZATION_PCT
                ),
                "ComparisonOperator": "GreaterThanOrEqualToThreshold",
                "TreatMissingData": "missing",
                "Metrics": [
                    {
                        "Id": "ecs_memory_utilization",
                        "Label": "ECS Memory Utilization",
                        "ReturnData": True,
                        "Expression": 'SELECT AVG(MemoryUtilization) FROM SCHEMA("AWS/ECS", ClusterName,ServiceName)',
                        "Period": 60,
                    }
                ],
            },
        )

    def _create_alb_alarms(self):
        CfnResource(
            self,
            "ALB5xxErrorAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "MetricName": "HTTPCode_ELB_5XX_Count",
                "Namespace": globals.CLOUDWATCH_ALARM_NAMESPACE,
                "Statistic": "Average",
                "Dimensions": [
                    {
                        "Name": "LoadBalancer",
                        "Value": f"{self.prebid_alb.load_balancer_full_name}",
                    }
                ],
                "Period": 60,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": 0,  # Set the threshold to 0% (error rate > 0%)
                "ComparisonOperator": "GreaterThanThreshold",
                "TreatMissingData": "missing",
            },
        )

        CfnResource(
            self,
            "ALB4xxErrorAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "MetricName": "HTTPCode_ELB_4XX_Count",
                "Namespace": globals.CLOUDWATCH_ALARM_NAMESPACE,
                "Statistic": "Average",
                "Dimensions": [
                    {
                        "Name": "LoadBalancer",
                        "Value": f"{self.prebid_alb.load_balancer_full_name}",
                    }
                ],
                "Period": 60,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": 1,  # Set the threshold to 1% (error rate > 1%)
                "ComparisonOperator": "GreaterThanThreshold",
                "TreatMissingData": "missing",
            },
        )

        CfnResource(
            self,
            "ALBTargetResponseTimeAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "MetricName": "TargetResponseTime",
                "Namespace": globals.CLOUDWATCH_ALARM_NAMESPACE,
                "Statistic": "Average",
                "Dimensions": [
                    {
                        "Name": "LoadBalancer",
                        "Value": self.prebid_alb.load_balancer_full_name,
                    }
                ],
                "Period": 60,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": 1,  # Set the threshold to 1 second (response time > 1s)
                "ComparisonOperator": "GreaterThanThreshold",
                "TreatMissingData": "missing",
            },
        )

        CfnResource(
            self,
            "ALBRequestsAnomalyAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "Dimensions": [],
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "ThresholdMetricId": "ad1",
                "ComparisonOperator": "LessThanLowerOrGreaterThanUpperThreshold",
                "TreatMissingData": "missing",
                "Metrics": [
                    {
                        "Id": "m1",
                        "ReturnData": True,
                        "MetricStat": {
                            "Metric": {
                                "Namespace": globals.CLOUDWATCH_ALARM_NAMESPACE,
                                "MetricName": "RequestCount",
                                "Dimensions": [
                                    {
                                        "Name": "LoadBalancer",
                                        "Value": self.prebid_alb.load_balancer_full_name,
                                    }
                                ],
                            },
                            "Period": 60,
                            "Stat": "Average",
                        },
                    },
                    {
                        "Id": "ad1",
                        "Label": "RequestCount (expected)",
                        "ReturnData": True,
                        "Expression": globals.ANOMALY_DETECTION_BAND_2,
                    },
                ],
            },
        )

    def _create_efs_alarms(self):
        CfnResource(
            self,
            "EFSPercentIOLimitAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "MetricName": "PercentIOLimit",
                "Namespace": "AWS/EFS",
                "Statistic": "Average",
                "Dimensions": [
                    {"Name": "FileSystemId", "Value": self.prebid_fs.file_system_id}
                ],
                "Period": 60,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": 100,  # Set threshold to 100% (trigger if >= 100%)
                "ComparisonOperator": "GreaterThanOrEqualToThreshold",
                "TreatMissingData": "missing",
            },
        )

    def _create_nat_alarms(self):
        for public_subnet in self.prebid_vpc.public_subnets:
            CfnResource(
                self,
                f"NATPortAllocationErrorAlarm-{public_subnet}",
                type=globals.CLOUDWATCH_ALARM_TYPE,
                properties={
                    "ActionsEnabled": False,
                    "MetricName": "ErrorPortAllocation",
                    "Namespace": "AWS/NATGateway",
                    "Statistic": "Sum",
                    "Dimensions": [
                        {"Name": "NatGatewayId", "Value": str(public_subnet)}
                    ],
                    "Period": 60,
                    "EvaluationPeriods": 1,
                    "DatapointsToAlarm": 1,
                    "Threshold": 0,  # Set threshold to 0 (trigger if > 0)
                    "ComparisonOperator": "GreaterThanThreshold",
                    "TreatMissingData": "missing",
                },
            )

            CfnResource(
                self,
                f"NATPacketsDropCountAlarm-{public_subnet}",
                type=globals.CLOUDWATCH_ALARM_TYPE,
                properties={
                    "ActionsEnabled": False,
                    "MetricName": "PacketsDropCount",
                    "Namespace": "AWS/NATGateway",
                    "Statistic": "Sum",
                    "Dimensions": [
                        {"Name": "NatGatewayId", "Value": str(public_subnet)}
                    ],
                    "Period": 60,
                    "EvaluationPeriods": 1,
                    "DatapointsToAlarm": 1,
                    "Threshold": 0,  # Set threshold to 0 (trigger if > 0)
                    "ComparisonOperator": "GreaterThanThreshold",
                    "TreatMissingData": "missing",
                },
            )

    def _create_cloudfront_alarms(self):
        CfnResource(
            self,
            "CloudFront4xxErrorRateAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "MetricName": "4xxErrorRate",
                "Namespace": globals.CLOUD_FRONT_NAMESPACE,
                "Statistic": "Average",
                "Dimensions": [
                    {"Name": "Region", "Value": "Global"},
                    {
                        "Name": "DistributionId",
                        "Value": self.prebid_cloudfront_distribution.distribution_id,
                    },
                ],
                "Period": 60,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": 1,  # Set threshold to 1% (trigger if > 1%)
                "ComparisonOperator": "GreaterThanThreshold",
                "TreatMissingData": "missing",
            },
        )

        CfnResource(
            self,
            "CloudFront5xxErrorRateAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "MetricName": "5xxErrorRate",
                "Namespace": globals.CLOUD_FRONT_NAMESPACE,
                "Statistic": "Average",
                "Dimensions": [
                    {"Name": "Region", "Value": "Global"},
                    {
                        "Name": "DistributionId",
                        "Value": self.prebid_cloudfront_distribution.distribution_id,
                    },
                ],
                "Period": 60,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": 0,  # Set threshold to 0% (trigger if > 0%)
                "ComparisonOperator": "GreaterThanThreshold",
                "TreatMissingData": "missing",
            },
        )

        CfnResource(
            self,
            "CloudFrontTotalErrorRateAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "MetricName": "TotalErrorRate",
                "Namespace": globals.CLOUD_FRONT_NAMESPACE,
                "Statistic": "Average",
                "Dimensions": [
                    {"Name": "Region", "Value": "Global"},
                    {
                        "Name": "DistributionId",
                        "Value": self.prebid_cloudfront_distribution.distribution_id,
                    },
                ],
                "Period": 60,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": 1,  # Set threshold to 1% (trigger if > 1%)
                "ComparisonOperator": "GreaterThanThreshold",
                "TreatMissingData": "missing",
            },
        )

        CfnResource(
            self,
            "CloudFrontRequestsAnomalyAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "Dimensions": [],
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "ThresholdMetricId": "ad1",
                "ComparisonOperator": "LessThanLowerOrGreaterThanUpperThreshold",
                "TreatMissingData": "missing",
                "Metrics": [
                    {
                        "Id": "m1",
                        "ReturnData": True,
                        "MetricStat": {
                            "Metric": {
                                "Namespace": globals.CLOUD_FRONT_NAMESPACE,
                                "MetricName": "Requests",
                                "Dimensions": [
                                    {"Name": "Region", "Value": "Global"},
                                    {
                                        "Name": "DistributionId",
                                        "Value": self.prebid_cloudfront_distribution.distribution_id,
                                    },
                                ],
                            },
                            "Period": 60,
                            "Stat": "Average",
                        },
                    },
                    {
                        "Id": "ad1",
                        "Label": "Requests (expected)",
                        "ReturnData": True,
                        "Expression": globals.ANOMALY_DETECTION_BAND_2,
                    },
                ],
            },
        )

    def _create_waf_alarms(self):
        CfnResource(
            self,
            "WAFBlockedRequestsAnomalyAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "Dimensions": [],
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "ThresholdMetricId": "ad1",
                "ComparisonOperator": "GreaterThanUpperThreshold",
                "TreatMissingData": "missing",
                "Metrics": [
                    {
                        "Id": "m1",
                        "ReturnData": True,
                        "MetricStat": {
                            "Metric": {
                                "Namespace": "AWS/WAFV2",
                                "MetricName": "BlockedRequests",
                                "Dimensions": [
                                    {
                                        "Name": "WebACL",
                                        "Value": str(self.waf_webacl_name),
                                    },
                                    {"Name": "Rule", "Value": "ALL"},
                                ],
                            },
                            "Period": 60,
                            "Stat": "Average",
                        },
                    },
                    {
                        "Id": "ad1",
                        "Label": "BlockedRequests (expected)",
                        "ReturnData": True,
                        "Expression": globals.ANOMALY_DETECTION_BAND_2,
                    },
                ],
            },
        )

    def _create_glue_alarms(self):
        CfnResource(
            self,
            "GlueJobFailureAlarm",
            type=globals.CLOUDWATCH_ALARM_TYPE,
            properties={
                "ActionsEnabled": False,
                "MetricName": "glue.error.ALL",
                "Namespace": "Glue",
                "Statistic": "Sum",
                "Dimensions": [
                    {"Name": "JobName", "Value": self.glue_job_name},
                    {"Name": "JobRunId", "Value": "ALL"},
                ],
                "Period": 60,
                "EvaluationPeriods": 1,
                "DatapointsToAlarm": 1,
                "Threshold": 0,
                "ComparisonOperator": "GreaterThanThreshold",
                "TreatMissingData": "missing",
            },
        )
