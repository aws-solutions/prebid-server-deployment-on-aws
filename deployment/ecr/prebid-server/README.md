
### Prerequisite
* [Docker](https://docs.docker.com/engine/)


### Docker Commands for local development

* Build prebid-server image.
  `docker build -t prebid-server .`
* Run prebid-server image: 
 `docker run -v ./:/mnt/efs -v ~/.aws:/root/.aws -p 8080:8080 prebid-server`
* View prebid server log:  
  `tail -f ./logs/prebid-server.log`
* Check server to verify status `200 OK`, `{"application":{"status":"ok"}}`:
  `curl -i http://localhost:8080/status`


### Docker Config
* You can update `prebid-server-java` git tag release in `./config.json`, then run `docker build --no-cache -t prebid-server .`.


### Applying Git Patches for Build or New Changes
* [README-patches.md](README-patches.md)

