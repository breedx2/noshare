#!/bin/bash

MYDIR=$(dirname $0)
MYDIR=$(realpath "$MYDIR")
echo $MYDIR

if [ "${NOSHARE_PORT}" == "" ] ; then
	NOSHARE_PORT=20666
	echo "Defaulting to incoming port ${NOSHARE_PORT}"
fi

if [ "${NOSHARE_KEYS_DIR}" == "" ] ; then
	NOSHARE_KEYS_DIR="${MYDIR}/keys"
	echo "Defaulting keys dir to ${NOSHARE_KEYS_DIR}"
fi

MOUNT_DIR="${NOSHARE_KEYS_DIR}/mounted"

rm -rf "${MOUNT_DIR}"
mkdir "${MOUNT_DIR}"
PREFIX=$(tail -1 "${MYDIR}/prefix")

# echo $PREFIX

for f in $(find "${NOSHARE_KEYS_DIR}" -type f -name '*.pub') ; do
	echo configuring $f
	FN=$(basename "$f")
	echo -n "${PREFIX}" > "${MOUNT_DIR}/$FN"
	cat $f >> "${MOUNT_DIR}/$FN"
done

docker run -d --name noshare --restart=on-failure:5 \
        -p ${NOSHARE_PORT}:2222 \
        -v "${MOUNT_DIR}:/etc/pubkeys" \
        -e DOCKER_MODS=linuxserver/mods:openssh-server-ssh-tunnel \
        -e PUBLIC_KEY_DIR=/etc/pubkeys \
        -e USER_NAME=app \
        lscr.io/linuxserver/openssh-server
