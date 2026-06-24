"""Generate tracking URLs with UTM parameters (TSD §4.16)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def generate_tracking_url(
    base_url: str,
    experiment_id: str,
    variant_name: str,
    utm_source: str = "experiment",
    utm_medium: str = "ab_test",
    utm_campaign: str | None = None,
    additional_params: dict[str, str] | None = None,
) -> str:
    """Generate a tracking URL with UTM parameters for experiment tracking.

    Args:
        base_url: The base URL to append parameters to
        experiment_id: Experiment identifier
        variant_name: Name of the variant
        utm_source: UTM source parameter (default: "experiment")
        utm_medium: UTM medium parameter (default: "ab_test")
        utm_campaign: UTM campaign parameter (default: experiment_id)
        additional_params: Optional dict of additional query parameters

    Returns:
        URL string with UTM parameters appended

    Example:
        >>> generate_tracking_url("https://example.com/page", "exp123", "control")
        'https://example.com/page?utm_source=experiment&utm_medium=ab_test&utm_campaign=exp123&utm_content=control&experiment_id=exp123&variant=control'
    """
    # Parse existing URL
    parsed = urlparse(base_url)

    # Parse existing query parameters
    existing_params = parse_qs(parsed.query)

    # Flatten existing params (parse_qs returns lists)
    flat_params = {k: v[0] for k, v in existing_params.items()}

    # Add UTM parameters
    flat_params["utm_source"] = utm_source
    flat_params["utm_medium"] = utm_medium
    flat_params["utm_campaign"] = utm_campaign or experiment_id
    flat_params["utm_content"] = variant_name

    # Add experiment tracking parameters
    flat_params["experiment_id"] = experiment_id
    flat_params["variant"] = variant_name

    # Add any additional parameters
    if additional_params:
        flat_params.update(additional_params)

    # Reconstruct URL
    new_query = urlencode(flat_params)
    new_parsed = parsed._replace(query=new_query)

    return urlunparse(new_parsed)


def generate_tracking_urls(
    base_url: str,
    experiment_id: str,
    variants: list[str],
    utm_source: str = "experiment",
    utm_medium: str = "ab_test",
    utm_campaign: str | None = None,
) -> dict[str, str]:
    """Generate tracking URLs for multiple variants.

    Args:
        base_url: The base URL
        experiment_id: Experiment identifier
        variants: List of variant names
        utm_source: UTM source parameter
        utm_medium: UTM medium parameter
        utm_campaign: UTM campaign parameter

    Returns:
        Dict mapping variant names to their tracking URLs

    Example:
        >>> generate_tracking_urls("https://example.com", "exp123", ["control", "treatment"])
        {'control': 'https://...', 'treatment': 'https://...'}
    """
    urls = {}
    for variant in variants:
        urls[variant] = generate_tracking_url(
            base_url=base_url,
            experiment_id=experiment_id,
            variant_name=variant,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
        )
    return urls
