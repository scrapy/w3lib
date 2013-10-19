#!/usr/bin/env python

setup_args = dict(
    name='w3lib',
    version='1.5',
    license='BSD',
    description='Library of web-related functions',
    author='Scrapy project',
    author_email='info@scrapy.org',
    url='https://github.com/scrapy/w3lib',
    packages=['w3lib'],
    platforms=['Any'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet :: WWW/HTTP',
    ],
    requires=['six (>= 1.4.1)'],
)

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
else:
    setup_args['install_requires'] = ['six >= 1.4.1']

setup(**setup_args)

