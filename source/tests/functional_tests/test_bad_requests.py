# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import requests
import os

CLOUDFRONT_ENDPOINT = os.environ["CLOUDFRONT_ENDPOINT"]
contentType = "application/json"
method = "GET"


def test_request_rejected_by_waf_1():
    url = f"https://{CLOUDFRONT_ENDPOINT}/status/admine/password=xyz"
    response = requests.request(method, url)
    assert response.status_code == 403


def test_request_rejected_by_waf_2():
    url = f"https://{CLOUDFRONT_ENDPOINT}/logs/activity.log"
    response = requests.request(method, url)
    assert response.status_code == 403
