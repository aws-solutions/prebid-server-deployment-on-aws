### Prerequisite
* [Apache JMeter](https://jmeter.apache.org/)


````
$ jmeter -n -t prebid_server_test_plan.jmx -l log.jtl
````
### Test Plan
#### prebid_server_test_plan.jmx
This test plan uses several commercial bidding adapters in Prebid server configured to respond in test mode. The bidding adapters do not make connections over the Internet when invoked this way and respond with fixed data. This test plan is suitable for verifying basic operations of the deployed stack are working.



