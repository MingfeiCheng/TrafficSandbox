"""
Shared RPC client utility for test scripts.

Usage:
    from rpc_client import connect

    proxy = connect("tcp://127.0.0.1:10667")
    proxy.sim.reset()
"""

import zmq
from tinyrpc import RPCClient
from tinyrpc.protocols.msgpackrpc import MSGPACKRPCProtocol
from tinyrpc.transports.zmq import ZmqClientTransport


def _unwrap(result):
    """Unwrap @sandbox_api response envelope.

    RPC methods return {"status": "ok", "data": ...} on success.
    This extracts and returns just the "data" value.
    """
    if isinstance(result, dict) and "status" in result:
        if result["status"] == "ok":
            return result.get("data", result)
        if result["status"] == "error":
            raise RuntimeError(f"RPC error: {result.get('message', result)}")
    return result


class DotRPCProxy:
    """Proxy that supports dot-notation for nested RPC namespaces.

    Example:
        proxy.sim.reset()         -> calls RPC method "sim.reset"
        proxy.map.lane.get_all()  -> calls RPC method "map.lane.get_all"

    Responses are automatically unwrapped from the {"status", "data"} envelope.
    """

    def __init__(self, client, prefix="", one_way=False):
        self.client = client
        self.prefix = prefix
        self.one_way = one_way

    def __getattr__(self, name):
        new_prefix = f"{self.prefix}.{name}" if self.prefix else name
        return DotRPCProxy(self.client, new_prefix, self.one_way)

    def __call__(self, *args, **kwargs):
        flat_args = list(args)
        result = self.client.call(self.prefix, flat_args, {}, one_way=self.one_way)
        return _unwrap(result)


def connect(endpoint="tcp://127.0.0.1:10667"):
    """Create a DotRPCProxy connected to the sandbox server."""
    ctx = zmq.Context()
    transport = ZmqClientTransport.create(ctx, endpoint)
    client = RPCClient(MSGPACKRPCProtocol(), transport)
    return DotRPCProxy(client)
