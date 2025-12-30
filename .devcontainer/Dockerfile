# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.205.2/containers/javascript-node/.devcontainer/base.Dockerfile

FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye

RUN apt-get update && \
  apt-get install gnupg wget openvpn curl -y

# Copy Surfshark OpenVPN config and auth files
COPY openvpn-configs/ /etc/openvpn/

# Create entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Ensure container has necessary permissions for VPN
ENV OPENVPN_CONFIG=/etc/openvpn/tw-tai.prod.surfshark.comsurfshark_openvpn_udp.ovpn

# Add DNS
#COPY openvpn-configs/resolv.conf /etc/resolv.conf

#RUN openvpn --config $OPENVPN_CONFIG --auth-user-pass /etc/openvpn/auth.txt --daemon

# Run entrypoint script during build
RUN /entrypoint.sh

# Install node and npm using nvm
#RUN sudo curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash && sudo apt update -y && nvm install v24.11.1

# [Optional] Uncomment this section to install additional OS packages.
# RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
#     && apt-get -y install --no-install-recommends <your-package-list-here>

# [Optional] Uncomment if you want to install an additional version of node using nvm
# ARG EXTRA_NODE_VERSION=10
# RUN su node -c "source /usr/local/share/nvm/nvm.sh && nvm install ${EXTRA_NODE_VERSION}"

# [Optional] Uncomment if you want to install more global node modules
# RUN su node -c "npm install -g <your-package-list-here>"
