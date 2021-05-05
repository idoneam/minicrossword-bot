#!/bin/sh -l

# 1: vm key
# 2: ssh address
# 3: public key
# 4: ssh user
# 5: project dir
# 6: project mutex
# 7: image name
# 8: args

printf "$1" > private.key
chmod 400 private.key
if [ -z "$3" ]
then
    echo 'not verifying host key'
    strict='no'
else
    echo 'checking host key'
    strict='yes'
    printf "$2 $3" > host.pub
    chmod 644 host.pub
fi
ssh -o StrictHostKeyChecking="$strict" -o UserKnownHostsFile=host.pub -i private.key "$4@$2" "\
cd '$5' && \
setlock '.$6' sh -c '
docker pull $7 2>&1 && \
docker stop $6 2>&1 && \
docker rm $6 2>&1 && \
docker run -d --name=$6 $8 $7 2>&1' && \
rm '.$6'" 2> /dev/null