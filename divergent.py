import json

import arrow
import six
import treq

from twisted.internet import defer
from twisted.names import dns, error


_VERSION_RECORD = {
    4: dns.A,
    6: dns.AAAA,
}


_QUERY_RECORD = {
    dns.A: dns.Record_A,
    dns.AAAA: dns.Record_AAAA,
}


class Token(object):

    def __init__(self, token, expires=None, catalog=None):
        if isinstance(expires, six.string_types):
            expires = arrow.get(expires)

        self.token = token.encode("utf8")
        self.expires = expires
        self.catalog = catalog

    def __repr__(self):
        return "<Token(token=%s, expires=%s)>" % (self.token, self.expires)

    @classmethod
    def fromJSON(cls, data):
        data = json.loads(data)

        return cls(
            data["access"]["token"]["id"],
            expires=data["access"]["token"]["expires"],
            catalog={c["name"]: c for c in data["access"]["serviceCatalog"]},
        )

    @property
    def expired(self):
        return arrow.utcnow() >= self.expires


class Server(object):

    def __init__(self, address):
        self.address = address
        self.expires = arrow.utcnow().replace(hours=+24)

    @property
    def expired(self):
        return arrow.utcnow() >= self.expires


class RackspaceResolver(object):

    def __init__(self, domains, networks, username, apikey, region="IAD",
                 identity_url="https://identity.api.rackspacecloud.com/v2.0"):
        self.domains = domains
        self.networks = networks

        self._rackspace_username = username
        self._rackspace_apikey = apikey
        self._rackspace_region = region
        self._rackspace_identity_url = identity_url

        self._rackspace_token = None
        self._rackspace_servers = None

        self._servers = {}

    def _dynamicResponseRequired(self, query):
        if query.type == dns.A or query.type == dns.AAAA:
            for domain in self.domains:
                if query.name.name.endswith(domain):
                    return True

        return False

    def _setToken(self, token):
        self._rackspace_token = token
        return token

    def _authenticateRackspace(self):
        if (self._rackspace_token is not None
                and not self._rackspace_token.expired):
            return defer.succeed(self._rackspace_token)

        d = treq.post(
            self._rackspace_identity_url + "/tokens",
            data=json.dumps({
                "auth": {
                    "RAX-KSKEY:apiKeyCredentials": {
                        "username": self._rackspace_username,
                        "apiKey": self._rackspace_apikey,
                    }
                }
            }),
            headers={"Content-Type": "application/json"},
        )
        d.addCallback(treq.content)
        d.addCallback(Token.fromJSON)
        d.addCallback(self._setToken)

        return d

    def _getServers(self, token):
        for endpoint in token.catalog["cloudServersOpenStack"]["endpoints"]:
            if endpoint["region"] == self._rackspace_region:
                d = treq.get(
                    (endpoint["publicURL"] + "/servers/detail").encode("utf8"),
                    headers={"X-Auth-Token": [token.token]},
                )
                d.addCallback(treq.content)
                d.addCallback(lambda x: json.loads(x)["servers"])

                return d

        return defer.succeed([])

    def _getAddressForName(self, servers, name, query_type):
        for s in servers:
            if s["name"].lower() == name.lower():
                for network in self.networks:
                    for address in s.get("addresses", {}).get(network, []):
                        if _VERSION_RECORD[address["version"]] == query_type:
                            return address["addr"]

        return defer.fail(error.DomainError())

    def _responseForAddress(self, address, name, query_type):
        record_class = _QUERY_RECORD[query_type]
        records = [
            dns.RRHeader(name=name, payload=record_class(address=address)),
        ]

        return records, [], []

    def _doDynamicResponse(self, query):
        name = query.name.name

        # See if we have a cached value for this server or not.
        server = self._servers.get((name.lower(), query.type))
        if server is not None and not server.expired:
            resp = self._responseForAddress(server.address, name, query.type)
            d = defer.succeed(resp)
        else:
            # We don't, so get the address from Rackspace.
            d = self._authenticateRackspace()
            d.addCallback(self._getServers)
            d.addCallback(self._getAddressForName, name, query.type)
            d.addCallback(self._responseForAddress, name, query.type)

        return d

    def query(self, query, timeout=None):
        """
        Check if the query should be answered dynamically, otherwise dispatch
        to the fallback resolver.
        """
        if self._dynamicResponseRequired(query):
            return self._doDynamicResponse(query)
        else:
            return defer.fail(error.DomainError())
