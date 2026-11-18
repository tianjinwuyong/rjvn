# -*- coding: utf-8 -*-
"""
SSH Passwordless Setup using Paramiko
Connects to SSH server and adds public key to authorized_keys
"""

import paramiko
import os
import sys

def setup_passwordless_ssh(host, username, password):
    """Setup passwordless SSH by adding public key to remote server"""

    # Get public key
    key_path = os.path.expanduser("~/.ssh/id_ed25519.pub")
    if not os.path.exists(key_path):
        print("SSH key not found. Generating...")
        os.system('ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "factory@workstation" -q')

    with open(key_path, 'r') as f:
        pub_key = f.read().strip()

    print(f"Public key: {pub_key}")
    print(f"Connecting to {username}@{host}...")

    try:
        # Connect to server
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print("Authenticating...")
        client.connect(
            hostname=host,
            port=22,
            username=username,
            password=password,
            timeout=10,
            allow_agent=False,
            look_for_keys=False
        )

        print("Connected! Adding public key to authorized_keys...")

        # Create .ssh directory and authorized_keys file
        commands = [
            'mkdir -p ~/.ssh',
            f'echo "{pub_key}" >> ~/.ssh/authorized_keys',
            'chmod 700 ~/.ssh',
            'chmod 600 ~/.ssh/authorized_keys',
            'cat ~/.ssh/authorized_keys'
        ]

        for cmd in commands:
            stdin, stdout, stderr = client.exec_command(cmd)
            output = stdout.read().decode()
            if output:
                print(f"  {output.strip()}")

        client.close()

        print("\nKey added successfully!")
        print(f"\nTest connection (should not ask for password):")
        print(f"  ssh {username}@{host}")

        return True

    except paramiko.AuthenticationException:
        print("Authentication failed. Please check password.")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    # Default values
    host = "192.168.6.56"
    username = "wy"

    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        username = sys.argv[2]

    print("=" * 50)
    print("SSH Passwordless Setup")
    print("=" * 50)
    print(f"Host: {host}")
    print(f"User: {username}")
    print()

    # Get password securely
    try:
        import getpass
        password = getpass.getpass("Enter password: ")
    except:
        password = input("Enter password: ")

    setup_passwordless_ssh(host, username, password)
