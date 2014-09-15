divergent
=========

Divergent is a DNS server which can be used to rewrite DNS entries so that
they get internal private IPs instead of the public IPs in the primary DNS. It
is designed to be ran inside of a VPN so that accessing
``something.example.com`` externally to the VPN gets a public address and
``something.example.com`` internal to the VPN gets a private address.
