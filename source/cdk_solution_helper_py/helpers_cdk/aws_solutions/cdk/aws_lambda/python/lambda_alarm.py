# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from constructs import Construct
from aws_cdk import Duration
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_cloudwatch as cloudwatch
import aws_cdk.aws_iam as iam

from aws_solutions.cdk.cfn_nag import add_cfn_nag_suppressions, CfnNagSuppression


# Alarm used for Solution lambda functions to alarm when lambda error or quota throttle
class SolutionsLambdaFunctionAlarm(Construct):
    def __init__(
            self,
            scope: Construct,
            id: str,
            alarm_name: str,
            lambda_function: lambda_.Function,
    ):
        throttles_metric = lambda_function.metric("Throttles", period=Duration.seconds(60))
        errors_metric = lambda_function.metric("Errors", period=Duration.seconds(60))

        super().__init__(scope, id)

        throttles_alarm = cloudwatch.Alarm(
            self,
            id=f'{id}-throttles',
            metric=throttles_metric,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        )

        errors_alarm = cloudwatch.Alarm(
            self,
            id=f'{id}-errors',
            metric=errors_metric,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            threshold=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
        )

