from setuptools import setup, find_packages


setup(
    name="w3lib",
    version="2.1.1",
    license="BSD",
    description="Library of web-related functions",
    author="Scrapy project",
    author_email="info@scrapy.org",
    url="https://github.com/scrapy/w3lib",
    packages=find_packages(exclude=("tests", "tests.*")),
    package_data={
        "w3lib": ["py.typed"],
    },
    include_package_data=True,
    zip_safe=False,
    platforms=["Any"],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Internet :: WWW/HTTP",
    ],
)
