import os
from setuptools import setup, find_packages, Extension


# https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html#distributing-cython-modules
def no_cythonize(extensions, **_ignore):
    for extension in extensions:
        sources = []
        for sfile in extension.sources:
            path, ext = os.path.splitext(sfile)
            if ext in (".pyx", ".py"):
                if extension.language == "c++":
                    ext = ".cpp"
                else:
                    ext = ".c"
                sfile = path + ext
            sources.append(sfile)
        extension.sources[:] = sources
    return extensions

extensions = [
    Extension(f"w3lib._{name}", [f"w3lib/_{name}.pyx"])
    for name in (
        "infra",
        "rfc2396",
        "rfc3986",
        "rfc5892",
        "types",
        "url",
        "util",
        "utr46",
    )
]

if bool(int(os.getenv("CYTHONIZE", 0))):
    from Cython.Build import cythonize
    compiler_directives = {"language_level": 3}
    extensions = cythonize(extensions, compiler_directives=compiler_directives)
else:
    extensions = no_cythonize(extensions)

setup(
    name="w3lib",
    version="2.1.2",
    license="BSD",
    description="Library of web-related functions",
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
    python_requires=">=3.8",
    install_requires=[
        "idna",
    ],
    ext_modules=extensions,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Topic :: Internet :: WWW/HTTP",
    ],
)
