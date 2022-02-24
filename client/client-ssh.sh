#!/bin/bash

ssh -p 20666 \
	-o "StrictHostKeyChecking=no" \
	-o "UserKnownHostsFile=/dev/null" \
	-i /home/jason/noshare/id_rsa app@localhost
