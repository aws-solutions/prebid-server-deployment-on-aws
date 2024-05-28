# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import random
import os
import time
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def lambda_handler(event, _):
    try:
        BID_RESPONSES_DELAY_PERCENTAGE = float(os.environ['BID_RESPONSES_DELAY_PERCENTAGE'])
        BID_RESPONSES_TIMEOUT_PERCENTAGE = float(os.environ['BID_RESPONSES_TIMEOUT_PERCENTAGE'])

        A_BID_RESPONSE_DELAY_PROBABILITY = float(os.environ['A_BID_RESPONSE_DELAY_PROBABILITY'])
        A_BID_RESPONSE_TIMEOUT_PROBABILITY = float(os.environ['A_BID_RESPONSE_TIMEOUT_PROBABILITY'])
    except Exception as e:
        logger.exception("Fail to read environment variables", e)
        raise e

    ad_request = json.loads(event["body"])
    tmax_in_millis = ad_request["tmax"]
    tmax_in_seconds = tmax_in_millis * 0.001

    if random.random() < BID_RESPONSES_DELAY_PERCENTAGE * A_BID_RESPONSE_DELAY_PROBABILITY:
        logger.info("Simulate delayed Bid Response")
        delay_in_seconds = random.random() * tmax_in_seconds
        time.sleep(delay_in_seconds)

    if random.random() < BID_RESPONSES_TIMEOUT_PERCENTAGE * A_BID_RESPONSE_TIMEOUT_PROBABILITY:
        logger.info("Simulate timeout scenario")
        timeout = 2 * tmax_in_seconds
        time.sleep(timeout)

    bid_response = {
        "id": "request_id",
        "seatbid": [
            {
                "bid": [
                    {
                        "id": "bid_id_1",
                        "impid": "imp_id_1",
                        "price": 3.33,
                        "crid": "creativeId"
                    },
                    {
                        "id": "bid_id_2",
                        "impid": "imp_id_1",
                        "price": 5.55,
                        "crid": "creativeId"
                    },
                    {
                        "id": "bid_id_3",
                        "impid": "imp_id_2",
                        "price": 5.55,
                        "crid": "creativeId"
                    },
                    {
                        "id": "bid_id_4",
                        "impid": "imp_id_2",
                        "price": 8.55,
                        "crid": "creativeId"
                    },
                    {
                        "id": "bid_id_5",
                        "impid": "imp_id_2",
                        "price": 100.0,
                        "crid": "creativeId"
                    }
                ]
            }
        ]
    }

    return {
        'statusCode': 200,
        'body': json.dumps(bid_response)
    }
