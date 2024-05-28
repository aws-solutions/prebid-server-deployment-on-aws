# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from pathlib import Path

from aws_cdk import App, Aspects
from aws_solutions.cdk import CDKSolution

from prebid_server.prebid_server_stack import PrebidServerStack
from prebid_server.app_registry_aspect import AppRegistry

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
    prebid_server_stack = PrebidServerStack(
        app,
        PrebidServerStack.name,
        description=PrebidServerStack.description,
        template_filename=PrebidServerStack.template_filename,
        synthesizer=synthesizer(),
    )
    Aspects.of(app).add(AppRegistry(prebid_server_stack, f"AppRegistry-{prebid_server_stack.name}"))
    return app.synth(validate_on_synthesis=True, skip_validation=False)


if __name__ == "__main__":
    build_app()
