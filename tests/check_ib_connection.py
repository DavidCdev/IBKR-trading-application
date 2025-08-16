import asyncio
import socket
from ib_async import IB


def check_port(host, port):
    """Check if a port is open"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


async def test_connection(host, port, client_id):
    """Test IB connection on specific host/port/client_id"""
    ib = IB()
    try:
        print(f"Testing connection to {host}:{port} with client ID {client_id}...")
        await ib.connectAsync(host, port, clientId=client_id)
        print(f"✓ SUCCESS: Connected to {host}:{port} with client ID {client_id}")
        ib.disconnect()
        return True
    except Exception as e:
        print(f"✗ FAILED: {host}:{port} with client ID {client_id} - {e}")
        return False


async def main():
    """Check common IB connection configurations"""
    host = '127.0.0.1'
    
    # Common IB ports
    ports = [
        (7496, "TWS Live Trading"),
        (7497, "IB Gateway Live Trading"), 
        (7498, "TWS Paper Trading"),
        (7499, "IB Gateway Paper Trading")
    ]
    
    print("=== IB Connection Port Checker ===\n")
    
    # Check which ports are open
    print("Checking which ports are open:")
    open_ports = []
    for port, description in ports:
        if check_port(host, port):
            print(f"✓ Port {port} ({description}) is open")
            open_ports.append(port)
        else:
            print(f"✗ Port {port} ({description}) is closed")
    
    print(f"\nFound {len(open_ports)} open port(s): {open_ports}")
    
    if not open_ports:
        print("\n❌ No IB ports are open. Please check if TWS or IB Gateway is running.")
        return
    
    # Test connections on open ports
    print("\n=== Testing IB Connections ===")
    
    for port in open_ports:
        # Test with different client IDs
        for client_id in [1, 2, 3]:
            await test_connection(host, port, client_id)
            await asyncio.sleep(0.5)  # Small delay between tests
    
    print("\n=== Summary ===")
    print("If you see SUCCESS messages above, those configurations work.")
    print("Use those host/port/client_id values in your IBDataCollector.")


if __name__ == "__main__":
    asyncio.run(main())
