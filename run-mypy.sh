#!/bin/bash

set -e

mypy --txt-report . w3lib tests
