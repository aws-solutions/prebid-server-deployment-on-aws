# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0


import os
import json
import logging
import requests
from datetime import datetime, timedelta
from aws_solutions.core.helpers import get_service_client

SOLUTION_ID = os.environ["SOLUTION_ID"]
SOLUTION_VERSION = os.environ["SOLUTION_VERSION"]
METRICS_NAMESPACE = os.environ["METRICS_NAMESPACE"]
SEND_ANONYMIZED_DATA = os.environ["SEND_ANONYMIZED_DATA"]
STACK_NAME = os.environ["STACK_NAME"]

SECONDS_IN_A_DAY = 86400

DT_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Format log messages like this:
formatter = logging.Formatter("{%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
# Clear the default logger before attaching the custom logging handler
# in order to avoid duplicating each log message:
logging.getLogger().handlers.clear()
# Attach the custom logging handler:
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

METRICS_ENDPOINT = "https://metrics.awssolutionsbuilder.com/generic"


class CloudwatchMetricsReport:
    def __init__(self, **kwargs):
        self.cloudwatch_client = get_service_client("cloudwatch")
        self.secrets_manager_client = get_service_client("secretsmanager")
        self.ec2_client = get_service_client("ec2")
        self.timestamp = datetime.utcnow()
        self.end_time = datetime.utcnow()
        self.start_time = self.end_time - timedelta(seconds=SECONDS_IN_A_DAY)
        self.statistics = ["Sum", "Minimum", "Maximum"]
        self.uuid = self.get_uuid()
        self.event = kwargs["event"]
        self.context = kwargs["context"]

    def data_init(self):
        return {"Data": {}, "MetricData": {}}

    def resolve_dt_time_format(self, datetime_obj):
        return datetime_obj.strftime(DT_TIME_FORMAT)

    def sum_datapoints(self, datapoints, stat="Sum"):
        if len(datapoints) > 1:
            logger.warning(
                "Got "
                + str(len(datapoints))
                + " datapoints but only expected one datapoint since period is one day and start/end time spans one day."
            )
        total = 0
        for datapoint in datapoints:
            # There should only be one datapoint since period is one day and
            # start/end time spans one day, but if there is more than one datapoint
            # then sum them together:
            total += datapoint.get(stat, 1)
        return total

    def get_metric_statistics(
        self, metrics_namespace, metric_name, statistics, dimensions
    ):
        return self.cloudwatch_client.get_metric_statistics(
            Namespace=metrics_namespace,
            MetricName=metric_name,
            StartTime=self.resolve_dt_time_format(self.start_time),
            EndTime=self.resolve_dt_time_format(self.end_time),
            Period=SECONDS_IN_A_DAY,
            Statistics=statistics,
            Dimensions=dimensions,
        )

    def prepare_metric_data(
        self, metric_tag, metric_name, response, sum_all_datapoints=True
    ):
        data = self.data_init()
        datapoints = response.get("Datapoints", [])
        # Add datapoints to the reporting payload:
        if datapoints:
            # Add the sum to the reporting payload:
            if metric_tag:
                metric_tag = f"{metric_tag}-"
            else:
                metric_tag = ""

            data["Data"][f"{metric_tag}{metric_name}"] = self.sum_datapoints(datapoints)
            if sum_all_datapoints:
                data["Data"]["datapoints"] = {
                    "SampleCount": self.sum_datapoints(datapoints, "SampleCount"),
                    "Average": self.sum_datapoints(datapoints, "Average"),
                    "Sum": self.sum_datapoints(datapoints, "Sum"),
                    "Minimum": self.sum_datapoints(datapoints, "Minimum"),
                    "Maximum": self.sum_datapoints(datapoints, "Maximum"),
                    "Unit": datapoints[0].get("Unit"),
                    "Timestamp": self.timestamp,
                }
        return data["Data"]

    def get_generic_metrics(self, metrics_to_sum, metric_tag=""):
        data = self.data_init()
        for metric_name in metrics_to_sum:
            # Sum all values for the metric over the past 24 hours:
            lambda_stat_response = self.get_metric_statistics(
                metrics_namespace=METRICS_NAMESPACE,
                metric_name=metric_name,
                statistics=self.statistics,
                dimensions=[{"Name": "stack-name", "Value": STACK_NAME}],
            )
            data["Data"].update(
                self.prepare_metric_data(
                    response=lambda_stat_response,
                    metric_name=metric_name,
                    metric_tag=metric_tag,
                    sum_all_datapoints=False,
                )
            )
        return data

    def get_cloudformation_metrics(self):
        metrics_to_sum = [
            "CloudFormation-CreateUpdate",
        ]
        return self.get_generic_metrics(metrics_to_sum)

    def get_lambda_metrics(self):
        metrics_to_sum = [
            "DeleteEfsFiles",
            "StartGlueJob",
        ]
        return self.get_generic_metrics(metrics_to_sum, "Lambda")

    def get_cloudfront_metrics(self):
        # Cloudfront
        data = self.data_init()
        metric_tag = "CloudFront"
        namespace = f"AWS/{metric_tag}"
        cf_cw_response = self.cloudwatch_client.list_metrics(
            Namespace=namespace,
            Dimensions=[
                {"Name": "DistributionId", "Value": os.environ["CF_DISTRIBUTION_ID"]},
                {"Name": "Region", "Value": "Global"},
            ],
        )
        for cf_cw_metric in cf_cw_response.get("Metrics", []):
            cf_response = self.get_metric_statistics(
                metrics_namespace=namespace,
                metric_name=cf_cw_metric["MetricName"],
                statistics=self.statistics,
                dimensions=cf_cw_metric["Dimensions"],
            )
            data["Data"].update(
                self.prepare_metric_data(
                    response=cf_response,
                    metric_name=cf_cw_metric["MetricName"],
                    metric_tag=metric_tag,
                )
            )
            metric = f"{metric_tag}-{cf_cw_metric['MetricName']}"
            if not data["MetricData"].get(metric):
                data["MetricData"][metric] = {}
            data["MetricData"][metric].update(
                {
                    "value": data["Data"][metric],
                    "dimensions": cf_cw_metric["Dimensions"],
                    "datapoints": data["Data"].pop("datapoints"),
                }
            )

        return data

    def get_nat_gateway_metrics(self):
        # NAT gateway
        metric_tag = "NATGateway"
        namespace = f"AWS/{metric_tag}"
        data = self.data_init()
        for subnet_id in json.loads(os.environ["SUBNET_IDS"]):
            nat_gateway_response = self.ec2_client.describe_nat_gateways(
                Filters=[
                    {
                        "Name": "subnet-id",
                        "Values": [
                            subnet_id,
                        ],
                    },
                ]
            )

            for nat_gateway in nat_gateway_response.get("NatGateways"):
                nat_gateway_id = nat_gateway.get("NatGatewayId")
                if nat_gateway_id:
                    nat_cw_response = self.cloudwatch_client.list_metrics(
                        Namespace=namespace,
                        Dimensions=[{"Name": "NatGatewayId", "Value": nat_gateway_id}],
                    )
                    for nat_metric in nat_cw_response.get("Metrics", []):
                        nat_cw_stat_response = self.get_metric_statistics(
                            metrics_namespace=namespace,
                            metric_name=nat_metric["MetricName"],
                            statistics=self.statistics,
                            dimensions=nat_metric["Dimensions"],
                        )

                        data["Data"].update(
                            self.prepare_metric_data(
                                response=nat_cw_stat_response,
                                metric_name=nat_metric["MetricName"],
                                metric_tag=metric_tag,
                            )
                        )
                        metric = f"{metric_tag}-{nat_metric['MetricName']}"
                        if not data["MetricData"].get(metric):
                            data["MetricData"][metric] = {}
                        data["MetricData"][metric].update(
                            {
                                "value": data["Data"][metric],
                                "dimensions": nat_metric["Dimensions"],
                                "datapoints": data["Data"].pop("datapoints"),
                            }
                        )

        return data

    def get_application_elb_metrics(self):
        # Load Balancer
        metric_tag = "ApplicationELB"
        namespace = f"AWS/{metric_tag}"
        data = self.data_init()
        elb_response = self.cloudwatch_client.list_metrics(
            Namespace=namespace,
            Dimensions=[
                {"Name": "LoadBalancer", "Value": os.environ["LOAD_BALANCER_NAME"]}
            ],
        )
        for elb_metric in elb_response.get("Metrics", []):
            elb_stat_response = self.get_metric_statistics(
                metrics_namespace=namespace,
                metric_name=elb_metric["MetricName"],
                statistics=["SampleCount", "Average", *self.statistics],
                dimensions=elb_metric["Dimensions"],
            )
            data["Data"].update(
                self.prepare_metric_data(
                    response=elb_stat_response,
                    metric_name=elb_metric["MetricName"],
                    metric_tag=metric_tag,
                )
            )
            metric = f"{metric_tag}-{elb_metric['MetricName']}"
            if not data["MetricData"].get(metric):
                data["MetricData"][metric] = {}
            data["MetricData"][metric].update(
                {
                    "value": data["Data"][metric],
                    "dimensions": elb_metric["Dimensions"],
                    "datapoints": data["Data"].pop("datapoints"),
                }
            )

        return data

    def get_uuid(self):
        return self.secrets_manager_client.get_secret_value(
            SecretId=f"{STACK_NAME}-anonymous-metrics-uuid"
        )["SecretString"]

    def get_metrics_report(self):
        data = {
            "Solution": SOLUTION_ID,
            "Version": SOLUTION_VERSION,
            "UUID": self.uuid,
            "TimestampUTC": self.resolve_dt_time_format(self.timestamp),
            "StartTime": self.resolve_dt_time_format(self.start_time),
            "EndTime": self.resolve_dt_time_format(self.end_time),
            **self.data_init(),
        }

        for metric_func in [
            "get_lambda_metrics",
            "get_cloudformation_metrics",
            "get_cloudfront_metrics",
            "get_nat_gateway_metrics",
            "get_application_elb_metrics",
        ]:
            metric_report_data = getattr(self, metric_func)()
            if metric_func not in ["get_lambda_metrics", "get_cloudformation_metrics"]:
                self.put_metric_data(metric_report_data["MetricData"])
            data["Data"].update(metric_report_data["Data"])

        data.pop("MetricData")
        return data

    def put_metric_data(self, metric_data):
        for metric_name, metric_data_value in metric_data.items():
            self.cloudwatch_client.put_metric_data(
                Namespace=METRICS_NAMESPACE,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Dimensions": metric_data_value["dimensions"],
                        "Unit": metric_data_value["datapoints"]["Unit"],
                        "Timestamp": metric_data_value["datapoints"]["Timestamp"],
                        "StatisticValues": {
                            "SampleCount": metric_data_value["datapoints"][
                                "SampleCount"
                            ],
                            "Sum": metric_data_value["datapoints"]["Sum"],
                            "Minimum": metric_data_value["datapoints"]["Minimum"],
                            "Maximum": metric_data_value["datapoints"]["Maximum"],
                        },
                    }
                ],
            )


def event_handler(event, context):
    """
    This function is the entry point.
    """
    logger.info("We got the following event:\n")
    logger.info("event:\n {s}".format(s=event))
    logger.info("context:\n {s}".format(s=context))
    send_metrics(event, context)


def send_metrics(event, context):
    """
    This function is responsible for reporting cloudwatch metrics.
    """

    cloudwatch_metrics_report = CloudwatchMetricsReport(event=event, context=context)
    data = cloudwatch_metrics_report.get_metrics_report()

    # Send metric data:
    if SEND_ANONYMIZED_DATA == "Yes":
        if data["Data"]:
            logger.info("Reporting the following data:")
            logger.info(json.dumps(data))
            response = requests.post(METRICS_ENDPOINT, json=data, timeout=5)
            logger.info(f"Response status code = {response.status_code}")
        else:
            logger.info("No data to report.")
    else:
        logger.info("User opted out of anonymous metric reporting.")
