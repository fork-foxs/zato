# -*- coding: utf-8 -*-

"""
Copyright (C) 2021, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# stdlib
from logging import getLogger
from typing import Optional as optional

# Requests
from requests import get as requests_get

# simdjson
from simdjson import loads

# Zato
from zato.client import AnyServiceInvoker
from zato.common.ext.dataclasses import dataclass, field
from zato.common.typing_ import from_dict

# ################################################################################################################################
# ################################################################################################################################

if 0:
    from requests import Response
    from typing import Callable
    from zato.client import ServiceInvokeResponse
    from zato.server.base.parallel import ParallelServer
    from zato.server.connection.server.rpc.config import RemoteServerInvocationCtx

    Callable = Callable
    ParallelServer = ParallelServer
    RemoteServerInvocationCtx = RemoteServerInvocationCtx
    Response = Response
    ServiceInvokeResponse = ServiceInvokeResponse

# ################################################################################################################################
# ################################################################################################################################

logger = getLogger('zato')

# ################################################################################################################################
# ################################################################################################################################

@dataclass(init=False)
class ServerInvocationResult:
    is_ok: bool = False
    has_data: bool = False
    data: object = ''
    error_info: object = ''

@dataclass
class PerPIDResponse:
    is_ok: bool = False
    pid: int = 0
    pid_data: optional[dict] = field(default_factory=dict)
    error_info: object = ''

# ################################################################################################################################
# ################################################################################################################################

class ServerInvoker:
    """ A base class for local and remote server invocations.
    """
    def __init__(self, parallel_server, cluster_name, server_name):
        # type: (ParallelServer) -> None

        # This parameter is used for local invocations only
        # to have access to self.parallel_server.invoke/.invoke_async/.invoke_all_pids
        self.parallel_server = parallel_server

        self.cluster_name = cluster_name
        self.server_name = server_name

    def invoke(self, *args, **kwargs):
        raise NotImplementedError(self.__class__)

    def invoke_async(self, *args, **kwargs):
        raise NotImplementedError(self.__class__)

    def invoke_all_pids(self, *args, **kwargs):
        # type: () -> ServerInvocationResult
        raise NotImplementedError(self.__class__)

# ################################################################################################################################
# ################################################################################################################################

class LocalServerInvoker(ServerInvoker):
    """ Invokes services directly on the current server, without any network-based RPC.
    """
    def invoke(self, *args, **kwargs):
        return self.parallel_server.invoke(*args, **kwargs)

# ################################################################################################################################

    def invoke_async(self, *args, **kwargs):
        return self.parallel_server.invoke_async(*args, **kwargs)

# ################################################################################################################################

    def invoke_all_pids(self, *args, **kwargs):
        return self.parallel_server.invoke_all_pids(*args, **kwargs)

# ################################################################################################################################
# ################################################################################################################################

class RemoteServerInvoker(ServerInvoker):
    """ Invokes services on a remote server using RPC.
    """
    def __init__(self, ctx):
        # type: (RemoteServerInvocationCtx) -> None
        super().__init__(None, ctx.cluster_name, ctx.server_name)
        self.invocation_ctx = ctx

        # We need to cover both HTTP and HTTPS connections to other servers
        protocol = 'https' if self.invocation_ctx.crypto_use_tls else 'http'

        # These two are used to ping each server right before an actual request is sent - with a short timeout,
        # this lets out quickly discover whether the server is up and running.
        self.ping_address = '{}://{}:{}/zato/ping'.format(protocol, self.invocation_ctx.address, self.invocation_ctx.port)
        self.ping_timeout = 1

        # Build the full address to the remote server
        self.address = '{}://{}:{}'.format(protocol, self.invocation_ctx.address, self.invocation_ctx.port)

        # Credentials to connect to the remote server with
        credentials = (self.invocation_ctx.username, self.invocation_ctx.password)

        # Now, we can build a client to the remote server
        self.invoker = AnyServiceInvoker(self.address, '/zato/internal/invoke', credentials)

# ################################################################################################################################

    def _invoke(self, invoke_func, service, request=None, *args, **kwargs):
        # type: (Callable, str, object) -> ServerInvocationResult

        # Optionally, ping the remote server to quickly find out if it is still available ..
        if self.invocation_ctx.needs_ping:
            requests_get(self.ping_address, timeout=self.ping_timeout)

        # .. actually invoke the server now ..
        response = invoke_func(service, request, skip_response_elem=True, *args, **kwargs) # type: ServiceInvokeResponse

        # .. build the results object ..
        out = ServerInvocationResult()
        out.is_ok = response.ok
        out.has_data = response.has_data
        out.data = {}
        out.error_info = response.details

        if response.ok:
            if response.has_data:
                for pid, pid_data in response.data.items():

                    per_pid_data = pid_data['pid_data']

                    if per_pid_data == '':
                        pid_data['pid_data'] = None

                    if per_pid_data and isinstance(per_pid_data, str) and per_pid_data[0] == '{':
                        pid_data['pid_data'] = loads(per_pid_data)

                    per_pid_response = from_dict(PerPIDResponse, pid_data) # type: PerPIDResponse
                    per_pid_response.pid = pid
                    out.data[pid] = per_pid_response

        # .. and return the result to our caller.
        return out

# ################################################################################################################################

    def invoke(self, *args, **kwargs):
        return self._invoke(self.invoker.invoke, *args, **kwargs)

# ################################################################################################################################

    def invoke_async(self, *args, **kwargs):
        return self._invoke(self.invoker.invoke_async, *args, **kwargs)

# ################################################################################################################################

    def invoke_all_pids(self, *args, **kwargs):
        kwargs['all_pids'] = True
        return self._invoke(self.invoker.invoke, *args, **kwargs)

# ################################################################################################################################
# ################################################################################################################################
