#!/bin/bash

#-L 6666:google.com:2222 \
ssh -p 20666 \
	-o "StrictHostKeyChecking=no" \
	-o "UserKnownHostsFile=/dev/null" \
	-N \
	-L 6666:localhost:2222 \
	-i /home/jason/noshare/id_rsa app@localhost
