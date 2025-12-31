#!/bin/sh
# Start OpenVPN in the background
openvpn --config /etc/openvpn/$OPENVPN_CONFIG --auth-user-pass /etc/openvpn/auth.txt --daemon

# Wait for VPN to connect
echo "Waiting for VPN connection..."
sleep 10

# Verify VPN connection
curl --silent https://ipinfo.io

if curl --silent https://ipinfo.io | grep -q "country"; then
    echo "VPN is connected."
else
    echo "VPN connection failed."
    exit 1
fi

# Add DNS
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# Bypass VPN for host subnet
#ip route add 172.17.0.0/16 via 172.17.0.1 dev eth0
# modified for custom docker subnet, it can be 17, 18, 19, etc.
ip route add 10.7.7.0/24 via 172.19.0.1 dev eth0

# Run the original entrypoint/command of the prebuilt image
exec "$@"
