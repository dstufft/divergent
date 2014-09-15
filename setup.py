import setuptools


setuptools.setup(
    name="divergent",
    version="0",
    install_requires=[
        "Twisted>=14.0",
        "pyOpenSSL>=0.14",
        "service-identity",
        "arrow",
        "six",
        "treq",
    ],
    py_modules=[
        "divergent",
    ],
    packages=[
        "twisted.plugins",
    ],
    package_data={
        "twisted": ["twisted/divergent_plugin.py"],
    }
)


# Make Twisted regenerate the dropin.cache, if possible. This is necessary
# because in a site-wide install, dropin.cache cannot be rewritten by
# normal users.
try:
    from twisted.plugin import IPlugin, getPlugins
except ImportError:
    pass
else:
    list(getPlugins(IPlugin))
