from setuptools import find_packages, setup

with open("README.rst", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="w3lib",
    version="2.3.1",
    license="BSD",
    description="Library of web-related functions",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    author="Scrapy project",
    author_email="info@scrapy.org",
    url="https://github.com/scrapy/w3lib",
    project_urls={
        "Documentation": "https://w3lib.readthedocs.io/en/latest/",
        "Source Code": "https://github.com/scrapy/w3lib",
        "Issue Tracker": "https://github.com/scrapy/w3lib/issues",
    },
    packages=find_packages(exclude=("tests", "tests.*")),
    package_data={
        "w3lib": ["py.typed"],
    },
    include_package_data=True,
    zip_safe=False,
    platforms=["Any"],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Internet :: WWW/HTTP",
    ],
)
