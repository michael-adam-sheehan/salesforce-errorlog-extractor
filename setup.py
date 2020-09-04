
from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='SFDCErrorLogExtractor',
    version='0.1.0',
    description='Salesforce Error Log Extractor',
    long_description=long_description,
    url='https://github.com/michael-adam-sheehan/salesforce-errorlog-extractor',
    author='Mike Sheehan',
    author_email='mike@teegrep.com',
    license='Apache License 2.0',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='salesforce sfdx error-logs',
    packages=find_packages(exclude=['tests']),
    install_requires=['chardet>=3.0.4', 'idna>=2.10', 'oauthlib>=3.1.0', 'pytz>=2020.1', 'requests>=2.24.0', 'requests-oauthlib>=1.3.0', 'urllib3>=1.25.10', 'responses>=0.10.16', 'tzlocal>=2.1'],
    setup_requires=['pytest-runner'],
    tests_require=['pytest']
)
