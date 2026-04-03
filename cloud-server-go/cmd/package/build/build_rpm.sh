#!/bin/bash
# Cloud Agent RPM Build Script
# This script generates an RPM spec file and builds the RPM package
# Usage: ./build_rpm.sh

set -e

AGENT_VERSION="1.0.0"
AGENT_NAME="cloud-agent"
RPM_NAME="cloud-agent"

echo "=== Cloud Agent RPM Build Script ==="
echo "Version: $AGENT_VERSION"

# Check if running as root for RPM build
if [ "$EUID" -eq 0 ]; then
    echo "Running as root - will build RPM directly"
    BUILD_AS_ROOT=true
else
    echo "Not running as root - will generate spec file only"
    BUILD_AS_ROOT=false
fi

# Check for required tools
check_tool() {
    if ! command -v $1 &> /dev/null; then
        echo "Error: $1 is required but not installed."
        return 1
    fi
    echo "Found: $1"
}

if [ "$BUILD_AS_ROOT" = true ]; then
    check_tool rpmbuild
    check_tool tar
fi

# Create RPM spec file
create_spec() {
    cat > ${AGENT_NAME}.spec << 'EOF'
Name:           cloud-agent
Version:        1.0.0
Release:        1%{?dist}
Summary:        CloudRealm Agent for distributed cluster management
License:        Apache-2.0
URL:            http://cloudrealm.com
BuildArch:      x86_64

Requires:       python3 >= 3.6, openssl, net-tools
Requires(post): systemd
Obsoletes:      cloud-agent < 1.0.0

%description
CloudRealm Agent is a lightweight node agent for distributed cluster management.
It provides service deployment, monitoring, and command execution capabilities.

%prep
# No prep needed - using prebuilt binaries

%build
# No compilation needed - Go binary already built

%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/usr/local/cloud-agent/bin
mkdir -p $RPM_BUILD_ROOT/usr/local/cloud-agent/python
mkdir -p $RPM_BUILD_ROOT/usr/local/cloud-agent/conf
mkdir -p $RPM_BUILD_ROOT/usr/local/cloud-agent/data
mkdir -p $RPM_BUILD_ROOT/usr/local/cloud-agent/log
mkdir -p $RPM_BUILD_ROOT/usr/local/cloud-agent/cache
mkdir -p $RPM_BUILD_ROOT/usr/lib/systemd/system

# Install Go binary
install -m 755 cloud-agent $RPM_BUILD_ROOT/usr/local/cloud-agent/bin/

# Install Python packages
cp -rf python/* $RPM_BUILD_ROOT/usr/local/cloud-agent/python/
chmod -R 755 $RPM_BUILD_ROOT/usr/local/cloud-agent/python

# Install config files
install -m 644 conf/cloud-agent.ini $RPM_BUILD_ROOT/usr/local/cloud-agent/conf/
install -m 755 conf/cloud-agent $RPM_BUILD_ROOT/usr/local/cloud-agent/conf/
install -m 755 conf/cloud-env.sh $RPM_BUILD_ROOT/usr/local/cloud-agent/conf/
install -m 644 conf/logging.conf.sample $RPM_BUILD_ROOT/usr/local/cloud-agent/conf/
install -m 644 conf/cloud-sudo.sh $RPM_BUILD_ROOT/usr/local/cloud-agent/conf/

# Install systemd service
cat > $RPM_BUILD_ROOT/usr/lib/systemd/system/cloud-agent.service << 'SYSTEMD'
[Unit]
Description=CloudRealm Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/cloud-agent/bin/cloud-agent -server http://localhost:8080
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
SYSTEMD

%post
if [ $1 -eq 1 ]; then
    # Initial installation
    systemctl daemon-reload || true
    systemctl enable cloud-agent || true
fi

%preun
if [ $1 -eq 0 ]; then
    # Package removal, not upgrade
    systemctl stop cloud-agent || true
    systemctl disable cloud-agent || true
fi

%postun
if [ $1 -eq 0 ]; then
    # Package removal complete
    systemctl daemon-reload || true
fi

%files
%defattr(-,root,root,-)
/usr/local/cloud-agent
/usr/lib/systemd/system/cloud-agent.service

%changelog
* Mon Mar 31 2025 CloudRealm <dev@cloudrealm.com> - 1.0.0-1
- Initial RPM package
EOF

    echo "Created: ${AGENT_NAME}.spec"
}

# Build RPM
build_rpm() {
    echo "Building RPM package..."

    # Set up RPM build environment
    mkdir -p ~/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

    # Copy package to SOURCES
    cp cloud-agent-${AGENT_VERSION}.tar.gz ~/rpmbuild/SOURCES/

    # Copy spec file
    cp ${AGENT_NAME}.spec ~/rpmbuild/SPECS/

    # Build RPM
    cd ~/rpmbuild
    rpmbuild -bb SPECS/${AGENT_NAME}.spec

    echo "RPM built successfully!"
    echo "Output: ~/rpmbuild/RPMS/x86_64/"
    ls -la RPMS/x86_64/
}

# Main
if [ "$BUILD_AS_ROOT" = true ]; then
    create_spec
    build_rpm
else
    create_spec
    echo ""
    echo "=== To build RPM on Linux server ==="
    echo "1. Upload this directory to your Linux server"
    echo "2. Run: tar -xzf cloud-agent-1.0.0.tar.gz"
    echo "3. Run: cd cloud-agent-1.0.0"
    echo "4. Run: sudo ./build_rpm.sh"
fi
