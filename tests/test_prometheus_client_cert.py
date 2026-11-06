from types import SimpleNamespace
from unittest.mock import patch

import pytest
from prometrix import PrometheusConfig

from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import (
    PrometheusMetricsService,
)
from robusta_krr.core.integrations.prometheus.prometheus_utils import generate_prometheus_config

APISERVER = "https://10.0.0.1:6443"
PROXY_URL = f"{APISERVER}/api/v1/namespaces/monitoring/services/prometheus:9090/proxy"


def make_service(url, cert_file="/tmp/cert", key_file="/tmp/key", host=APISERVER, api_client=True):
    service = PrometheusMetricsService.__new__(PrometheusMetricsService)
    service.url = url
    service.api_client = (
        SimpleNamespace(configuration=SimpleNamespace(host=host, cert_file=cert_file, key_file=key_file))
        if api_client
        else None
    )
    return service


@pytest.fixture
def outside_cluster():
    with patch(
        "robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service.settings"
    ) as settings:
        settings.inside_cluster = False
        yield settings


def test_client_cert_sent_to_apiserver_proxy(outside_cluster):
    assert make_service(PROXY_URL)._get_apiserver_client_cert() == ("/tmp/cert", "/tmp/key")


def test_client_cert_host_with_trailing_slash(outside_cluster):
    assert make_service(PROXY_URL, host=APISERVER + "/")._get_apiserver_client_cert() == ("/tmp/cert", "/tmp/key")


@pytest.mark.parametrize(
    "url",
    [
        "http://prometheus.example.com",
        "https://10.0.0.1:64430/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
        "https://10.0.0.1:6443.evil.example.com/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
    ],
)
def test_client_cert_not_sent_to_other_hosts(outside_cluster, url):
    assert make_service(url)._get_apiserver_client_cert() is None


def test_no_client_cert_in_kubeconfig(outside_cluster):
    assert make_service(PROXY_URL, cert_file=None, key_file=None)._get_apiserver_client_cert() is None


def test_no_client_cert_without_api_client(outside_cluster):
    assert make_service(PROXY_URL, api_client=False)._get_apiserver_client_cert() is None


def test_no_client_cert_inside_cluster(outside_cluster):
    outside_cluster.inside_cluster = True
    assert make_service(PROXY_URL)._get_apiserver_client_cert() is None


@pytest.mark.skipif(
    "client_cert" not in PrometheusConfig.__fields__, reason="installed prometrix has no client_cert support"
)
def test_prometheus_config_gets_client_cert():
    service = make_service(PROXY_URL)
    service.client_cert = ("/tmp/cert", "/tmp/key")
    config = generate_prometheus_config(url=PROXY_URL, headers={}, metrics_service=service)
    assert config.client_cert == ("/tmp/cert", "/tmp/key")
