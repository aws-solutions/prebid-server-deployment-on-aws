# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from pathlib import Path

from aws_cdk import App
from aws_solutions.cdk import CDKSolution

from bidding_server_simulator import BiddingServerSimulatorStack

solution = CDKSolution(cdk_json_path=Path(__file__).parent.absolute() / "cdk.json")

logger = logging.getLogger("cdk-helper")


def synthesizer():
    return CDKSolution(
        cdk_json_path=Path(__file__).parent.absolute() / "cdk.json"
    ).synthesizer


@solution.context.requires("SOLUTION_NAME")
@solution.context.requires("SOLUTION_ID")
@solution.context.requires("SOLUTION_VERSION")
@solution.context.requires("BUCKET_NAME")
def build_app(context):
    app = App(context=context)
    BiddingServerSimulatorStack(
        app,
        BiddingServerSimulatorStack.name,
        description=BiddingServerSimulatorStack.description,
        template_filename=BiddingServerSimulatorStack.template_filename,
        synthesizer=synthesizer(),
    )
    return app.synth(validate_on_synthesis=True, skip_validation=False)


if __name__ == "__main__":
    build_app()
