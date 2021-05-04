#!/bin/sh -l

# 1: vm key
# 2: vm address
# 3: vm session
# 4: project dir
# 5: project mutex
# 6: image name
# 7: args

printf "$1" > key.pem
chmod 400 key.pem
ssh -o StrictHostKeyChecking=no -i key.pem "$3@$2" "cd '$4' && setlock '.$5' sh -c '
docker pull $6 &&\
docker stop $5 &&\
docker rm $5 &&\
docker run -d --name=$5 $7 $6'" 2> /dev/null