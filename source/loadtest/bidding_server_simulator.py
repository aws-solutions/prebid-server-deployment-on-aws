# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

from aws_solutions.cdk import SolutionStack
from constructs import Construct
from aws_cdk import (
    Duration,
    Aws,
    aws_lambda as awslambda,
    aws_apigateway as apigateway, CfnParameter
)


class BiddingServerSimulatorStack(SolutionStack):
    name = "BiddingServerSimulator"
    description = "Bidding Server Simulator"
    template_filename = "bidding-server-simulator.template"

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.synthesizer.bind(self)

        self._resource_prefix = Aws.STACK_NAME

        self.response_delay_percentage = CfnParameter(
            self,
            "bidResponseDelayPercentage",
            description="Percentage of bid requests to get delayed response",
            type="Number",
            min_value=0,
            max_value=1,
            default=0
        )

        self.response_timeout_percentage = CfnParameter(
            self,
            "bidResponseTimeoutPercentage",
            description="Percentage of bid requests to get timeout response",
            type="Number",
            min_value=0,
            max_value=1,
            default=0
        )

        self.response_delay_probability = CfnParameter(
            self,
            "bidResponseDelayProbability",
            description="Probability for a Bid Response to be delay",
            type="Number",
            min_value=0,
            max_value=1,
            default=0
        )

        self.response_timeout_probability = CfnParameter(
            self,
            "bidResponseTimeoutProbability",
            description="Probability for a Bid Response to be timeout",
            type="Number",
            min_value=0,
            max_value=1,
            default=0
        )

        # Use Lambda to simulate a bidding server
        self._bidding_server_simulator = awslambda.Function(
            self,
            "biddingServerSimulator",
            function_name=f"{self._resource_prefix}-bidding-server-simulator",
            code=awslambda.Code.from_asset(os.path.join(f"{Path(__file__).parent}", "lambdas/bidder_simulator")),
            handler="handler.lambda_handler",
            environment={
                "SOLUTION_ID": self.node.try_get_context("SOLUTION_ID"),
                "SOLUTION_VERSION": self.node.try_get_context("SOLUTION_VERSION"),
                "BID_RESPONSES_DELAY_PERCENTAGE": self.response_delay_percentage.value_as_string,
                "BID_RESPONSES_TIMEOUT_PERCENTAGE": self.response_timeout_percentage.value_as_string,
                "A_BID_RESPONSE_DELAY_PROBABILITY": self.response_delay_probability.value_as_string,
                "A_BID_RESPONSE_TIMEOUT_PROBABILITY": self.response_timeout_probability.value_as_string,
            },
            description="Simulating a bidding server to send a Bid Response",
            timeout=Duration.minutes(1),
            memory_size=256,
            architecture=awslambda.Architecture.ARM_64,
            runtime=awslambda.Runtime.PYTHON_3_11,
        )

        # Bidding server endpoint to receive outbound Bid Request from the Prebid Server
        self._bidding_server_endpoint = apigateway.RestApi(
            self,
            "biddingServerEndpoint",
            endpoint_types=[apigateway.EndpointType.REGIONAL],
            deploy=True,
        )
        self._bidding_server_endpoint.root.add_method(
            "POST",
            apigateway.LambdaIntegration(self._bidding_server_simulator)
        )
