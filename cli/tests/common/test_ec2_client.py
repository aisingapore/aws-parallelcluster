# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance
# with the License. A copy of the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "LICENSE.txt" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and
# limitations under the License.
import os

import pytest
from assertpy import assert_that

from common.aws.aws_resources import InstanceTypeInfo
from common.boto3.common import AWSClientError
from common.boto3.ec2 import Ec2Client
from tests.common.dummy_aws_api import mock_aws_api
from tests.utils import MockedBoto3Request


@pytest.fixture()
def boto3_stubber_path():
    return "common.boto3.common.boto3"


@pytest.mark.parametrize(
    "region, free_tier_instance_type, default_instance_type, stub_boto3",
    [
        ("us-east-1", "t2.micro", "t2.micro", True),
        ("eu-north-1", "t3.micro", "t3.micro", True),
        ("us-gov-east-1", None, "t3.micro", True),
    ],
)
@pytest.mark.nomockdefaultinstance
def test_get_default_instance(boto3_stubber, region, free_tier_instance_type, default_instance_type, stub_boto3):
    os.environ["AWS_DEFAULT_REGION"] = region
    if free_tier_instance_type:
        response = {"InstanceTypes": [{"InstanceType": free_tier_instance_type}]}
    else:
        response = {"InstanceTypes": []}
    if stub_boto3:
        mocked_requests = [
            MockedBoto3Request(
                method="describe_instance_types",
                response=response,
                expected_params={
                    "Filters": [
                        {"Name": "free-tier-eligible", "Values": ["true"]},
                        {"Name": "current-generation", "Values": ["true"]},
                    ]
                },
            )
        ]

        boto3_stubber("ec2", mocked_requests)
    assert_that(Ec2Client().get_default_instance_type()).is_equal_to(default_instance_type)


@pytest.mark.parametrize("generate_error", [True, False])
def test_list_instance_types(boto3_stubber, generate_error):
    """Verify that list_instance_types behaves as expected."""
    dummy_message = "dummy error message"
    dummy_instance_types = ["c5.xlarge", "m6g.xlarge"]
    mocked_requests = [
        MockedBoto3Request(
            method="describe_instance_type_offerings",
            expected_params={},
            response=dummy_message
            if generate_error
            else {"InstanceTypeOfferings": [{"InstanceType": instance_type} for instance_type in dummy_instance_types]},
            generate_error=generate_error,
        )
    ]
    boto3_stubber("ec2", mocked_requests)
    if generate_error:
        error_message = "Error during execution of describe_instance_type_offerings. {0}".format(dummy_message)
        with pytest.raises(AWSClientError, match=error_message):
            Ec2Client().list_instance_types()
    else:
        return_value = Ec2Client().list_instance_types()
        assert_that(return_value).is_equal_to(dummy_instance_types)


@pytest.mark.parametrize(
    "instance_type, supported_architectures, error_message",
    [
        ("t2.micro", ["x86_64", "i386"], None),
        ("a1.medium", ["arm64"], None),
        ("valid.exotic.arch.instance", ["exoticArch"], None),
    ],
)
def test_get_supported_architectures(mocker, instance_type, supported_architectures, error_message):
    """Verify that get_supported_architectures_for_instance_type behaves as expected for various cases."""
    mock_aws_api(mocker)
    get_instance_types_info_patch = mocker.patch(
        "common.boto3.ec2.Ec2Client.get_instance_type_info",
        return_value=InstanceTypeInfo({"ProcessorInfo": {"SupportedArchitectures": supported_architectures}}),
    )
    observed_architectures = Ec2Client().get_supported_architectures(instance_type)
    expected_architectures = list(set(supported_architectures) & set(["x86_64", "arm64"]))
    assert_that(observed_architectures).is_equal_to(expected_architectures)

    get_instance_types_info_patch.assert_called_with(instance_type)
