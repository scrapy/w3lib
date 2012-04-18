from distutils.core import setup

setup(
    name='w3lib',
    version='1.2',
    license='BSD',
    description='Library of web-related functions',
    author='Scrapy project',
    author_email='info@scrapy.org',
    url='http://github.com/scrapy/w3lib',
    packages=['w3lib'],
    platforms = ['Any'],
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
    ]
)
