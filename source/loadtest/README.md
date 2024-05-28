# Load Test

## Deploy Bidding Server Simulator
1. `cd source/loadtest`
2. `cdk synth`
3. `cdk deploy`
4. Go to CloudFormation console and copy bidding server endpoint from `BiddingServerSimulator` stack Outputs.

## Add Bid Adapter Simulator
1. Prerequisite: Prebid Server and Bidding Server Simulator are deployed. 
2. Create a new revision for the task definition of Prebid Server in ECS console: 
   1. Update environment variable `AMT_ADAPTER_ENABLED` in  to `true`. 
   2. Add environment variable `AMT_BIDDING_SERVER_SIMULATOR_ENDPOINT` in ECS Task definitions and
      assign the endpoint of bidding server simulator as its value.
3. Update the revision of service of Prebid Server cluster to the revision created in step 2.

## Update or Create Test Plan in JMeter
1. Download [Apache JMeter](https://jmeter.apache.org/download_jmeter.cgi) and Install it.
2. Build test plan in JMeter. 
   1. Open an example test plan `source/loadtest/jmx/prebid_server_test_plan_using_amt_adapter.jmx` in JMeter. 
   2. Update the `url` in User Defined Variables. The value of `url` is the CloudFront endpoint of Prebid Server. 
   3. Optional: update HTTP Request under Thread Group. 
   4. Start the tests to verify the tests works properly with the Prebid Server.  

## Set Up Distributed Load Testing (DLT)
The [Distributed Load Testing on AWS](https://aws.amazon.com/solutions/implementations/distributed-load-testing-on-aws/) 
is used to automate the load tests. 
1. Follow its implementation guide to set up the DLT.
2. Use the test plan to start the load tests. 


## Use of Bidding Server Simulator
The bidding server simulator uses ApiGateway and Lambda to respond the bid requests from Prebid Server with bids.
The bidding server can simulate delayed and timeout bid response. 
The bid response returned by Lambda follows [OpenRTB specification](https://www.iab.com/wp-content/uploads/2016/03/OpenRTB-API-Specification-Version-2-5-FINAL.pdf#page=32).
```json
{
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
```
### Simulate BidResponse Delay
Two CloudFormation parameters are used to simulate delayed bid response, and can be adjusted in CloudFormation console.
* `BID_RESPONSES_DELAY_PERCENTAGE`: Percentage of bid requests that will get delayed response from bidder, ranging from 0 to 1. 
* `A_BID_RESPONSE_DELAY_PROBABILITY`: Probability for a bid response to be delay, ranging from 0 to 1.

By default, the simulation of delayed bid response are turned off. 

### Simulate BidResponse Timeout
Two CloudFormation parameters are used to simulate timeout bid response, and can be adjusted in CloudFormation console.
* `BID_RESPONSES_TIMEOUT_PERCENTAGE`: Percentage of bid requests that will get timeout response from bidder, ranging from 0 to 1. 
* `A_BID_RESPONSE_TIMEOUT_PROBABILITY`: Probability for a bid response to be timeout, ranging from 0 to 1.

By default, the simulation of timeout bid response are turned off. 

## Example Auction Request
Send post request to auction endpoint of Prebid Server with body data. 
```python
import requests

url = "https://prebid_cloudfront_endpoint/openrtb2/auction"

auction_request = {
    "id": "dsadfrggh",
    "imp": [
        {"id": "imp_id_1",
         "banner": {"w": 300, "h": 250},
         "ext": {
             "amt": {
                 "placementId": "dsdasf",
                 "bidFloor": 1,
                 "bidCeiling": 100000
             }
         }
         },
        {
            "id": "imp_id_2",
            "banner": {"w": 300, "h": 250},
            "ext": {
                "amt": {
                    "placementId": "dsdasfdsa",
                    "bidFloor": 1,
                    "bidCeiling": 50
                }
            }
        }
    ],
    "device": {
        "pxratio": 4.2,
        "dnt": 2,
        "language": "en",
        "ifa": "ifaId"
    },
    "site": {
        "page": "prebid.org",
        "publisher": {
            "id": "publisherId"
        }
    },
    "at": 1,
    "tmax": 5000,
    "cur": [
        "USD"
    ],
    "source": {
        "fd": 1,
        "tid": "tid"
    },
    "ext": {
        "prebid": {
            "targeting": {
                "pricegranularity": {
                    "precision": 2,
                    "ranges": [
                        {
                            "max": 20,
                            "increment": 0.1
                        }
                    ]
                }
            },
            "cache": {
                "bids": {}
            },
            "auctiontimestamp": 1000
        }
    },
    "regs": {"ext": {"gdpr": 0}}
}

x = requests.post(url, json=auction_request)
print(x.text)
```
*Note: The above Python code is an example. `prebid_cloudfront_endpoint` should be replaced 
with the actual CloudFront endpoint of Prebid Server deployed by users.* 