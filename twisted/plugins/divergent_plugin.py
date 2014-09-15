from zope.interface import implements

from twisted.names import client, dns, server
from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker, MultiService
from twisted.application import internet

from divergent import RackspaceResolver


class Options(usage.Options):

    optParameters = [
        ["username", "u", None, "The username for the Rackspace account."],
        ["api-key", "k", None, "The API Key for the Rackspace account."],
    ]

    def __init__(self, *args, **kwargs):
        super(Options, self).__init__(*args, **kwargs)

        self["domains"] = []
        self["networks"] = []

    def opt_port(self, portstr):
        try:
            self["port"] = int(portstr)
        except ValueError:
            raise usage.UsageError(
                "Specify an integer between 0 and 65535 as a port number."
            )

        if self['port'] >= 2 ** 16:
            raise usage.UsageError(
                "Specify an integer between 0 and 65535 as a port number."
            )
        elif self['port'] < 0:
            raise usage.UsageError(
                "Specify an integer between 0 and 65535 as a port number."
            )

    opt_p = opt_port

    def opt_domain(self, domain):
        self["domains"].append(domain)

    def opt_network(self, network):
        self["networks"].append(network)


class DivergentServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "divergent"
    description = (
        "Divergent is a DNS server which masquerades internal cloud IPs as "
        "public names."
    )
    options = Options

    def makeService(self, options):
        print((options["username"], options["api-key"]))
        tcpFactory = server.DNSServerFactory(
            clients=[
                RackspaceResolver(
                    domains=options["domains"],
                    networks=options["networks"],
                    username=options["username"],
                    apikey=options["api-key"],
                ),
                client.Resolver(resolv="/etc/resolv.conf"),
            ],
        )

        udpFactory = dns.DNSDatagramProtocol(tcpFactory)

        tcpServer = internet.TCPServer(options["port"], tcpFactory)
        udpServer = internet.UDPServer(options["port"], udpFactory)

        dnsService = MultiService()
        tcpServer.setServiceParent(dnsService)
        udpServer.setServiceParent(dnsService)

        return dnsService


serviceMaker = DivergentServiceMaker()
