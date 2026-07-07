"""Black-Scholes IV solver and option Greeks.

Pure-Python Newton-Raphson IV inversion + analytical Greeks. No scipy
dependency. Works for European Indian index options (ignores dividends).
"""
from __future__ import annotations

import math
from typing import Optional

SQRT_2PI = math.sqrt(2.0 * math.pi)


def _phi(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(*, S: float, K: float, T: float, r: float, sigma: float, opt: str) -> float:
    """Black-Scholes price (call or put). T in years."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        # at expiry — intrinsic value
        if opt == "C":
            return max(S - K, 0.0)
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt == "C":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def implied_vol(*, market_price: float, S: float, K: float, T: float, r: float,
                opt: str, max_iter: int = 60, tol: float = 1e-4) -> Optional[float]:
    """Newton-Raphson IV with a bisection fallback for deep ITM/OTM strikes."""
    if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None
    # ensure the price is above intrinsic (otherwise no real IV exists)
    intrinsic = max(S - K, 0.0) if opt == "C" else max(K - S, 0.0)
    if market_price <= intrinsic + 1e-6:
        # near-intrinsic premium — return tiny IV so Greeks remain finite
        return 1e-3
    # initial guess (Brenner-Subrahmanyam)
    sigma = math.sqrt(2.0 * math.pi / T) * (market_price / S) if S > 0 else 0.3
    sigma = max(0.01, min(sigma, 5.0))
    for _ in range(max_iter):
        price = bs_price(S=S, K=K, T=T, r=r, sigma=sigma, opt=opt)
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
        vega = S * _phi(d1) * sqrt_T
        if vega < 1e-8:
            break
        diff = price - market_price
        if abs(diff) < tol:
            return max(0.0, min(sigma, 5.0))
        sigma -= diff / vega
        if sigma <= 0:
            sigma = 1e-4
        if sigma > 5:
            sigma = 5.0
    # Bisection fallback in [1e-3, 5.0]
    lo, hi = 1e-3, 5.0
    p_lo = bs_price(S=S, K=K, T=T, r=r, sigma=lo, opt=opt)
    p_hi = bs_price(S=S, K=K, T=T, r=r, sigma=hi, opt=opt)
    if (p_lo - market_price) * (p_hi - market_price) > 0:
        # market price outside the BS range — return the closest extreme
        return lo if abs(p_lo - market_price) < abs(p_hi - market_price) else hi
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        p_mid = bs_price(S=S, K=K, T=T, r=r, sigma=mid, opt=opt)
        if abs(p_mid - market_price) < tol:
            return mid
        if (p_lo - market_price) * (p_mid - market_price) <= 0:
            hi, p_hi = mid, p_mid
        else:
            lo, p_lo = mid, p_mid
    return 0.5 * (lo + hi)


def greeks(*, S: float, K: float, T: float, r: float, sigma: float, opt: str) -> dict:
    """Analytical Greeks. Returns delta, gamma, vega, theta (per day), rho."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    pdf_d1 = _phi(d1)
    if opt == "C":
        delta = _norm_cdf(d1)
        theta_year = (-S * pdf_d1 * sigma / (2 * sqrt_T)
                      - r * K * math.exp(-r * T) * _norm_cdf(d2))
        rho = K * T * math.exp(-r * T) * _norm_cdf(d2)
    else:
        delta = _norm_cdf(d1) - 1.0
        theta_year = (-S * pdf_d1 * sigma / (2 * sqrt_T)
                      + r * K * math.exp(-r * T) * _norm_cdf(-d2))
        rho = -K * T * math.exp(-r * T) * _norm_cdf(-d2)
    gamma = pdf_d1 / (S * sigma * sqrt_T)
    vega = S * pdf_d1 * sqrt_T / 100.0  # per 1% vol
    theta = theta_year / 365.0  # per day
    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "vega": round(vega, 4),
        "theta": round(theta, 4),
        "rho": round(rho / 100.0, 4),
    }
