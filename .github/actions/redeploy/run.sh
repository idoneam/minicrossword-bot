#!/bin/sh -l

# 1: vm key
# 2: ssh address
# 3: project dir
# 4: project mutex
# 5: image name
# 6: args

printf "$1" > key.pem
chmod 400 key.pem
ssh -o StrictHostKeyChecking=no -i key.pem "$2" "\
cd '$3' && \
setlock '.$4' sh -c '
docker pull $5 2>&1 && \
docker stop $4 2>&1 && \
docker rm $4 2>&1 && \
docker run -d --name=$4 $6 $5 2>&1' && \
rm '.$4'" 2> /dev/null