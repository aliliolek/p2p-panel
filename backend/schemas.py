from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from constants import FIAT_BALANCE_REMARK_MARKER


class CredentialCreate(BaseModel):
    exchange: str = Field(..., description="Exchange identifier, e.g. bybit")
    account_label: Optional[str] = Field(
        default=None, description="Friendly name of the exchange account"
    )
    api_key: str = Field(..., description="Public API key")
    api_secret: str = Field(..., description="Secret API key")


class CredentialResponse(BaseModel):
    id: str
    exchange: str
    account_label: Optional[str]
    api_key_preview: str
    status: str
    last_check_at: Optional[datetime]
    last_check_response: Optional[Dict[str, Any]]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class CredentialListResponse(BaseModel):
    items: List[CredentialResponse]


class ApiInfoResponse(BaseModel):
    public_ip: Optional[str]
    ip_error: Optional[str] = None
    supported_exchanges: List[str]


class PendingOrder(BaseModel):
    order_id: str
    side: str
    token: Optional[str]
    status_code: Optional[int]
    status_label: Optional[str]
    fiat_currency: Optional[str]
    fiat_amount: Optional[float]
    price: Optional[float]
    crypto_amount: Optional[float]
    counterparty_name: Optional[str]
    counterparty_nickname: Optional[str]
    created_at: Optional[datetime]
    raw: Optional[Dict[str, Any]] = None


class AccountPendingOrders(BaseModel):
    credential_id: str
    account_label: Optional[str]
    exchange: str
    orders: List[PendingOrder]
    error: Optional[str] = None


class PendingOrdersResponse(BaseModel):
    accounts: List[AccountPendingOrders]


class AdItem(BaseModel):
    ad_id: str
    side: str
    token: Optional[str]
    fiat_currency: Optional[str]
    price: Optional[float]
    crypto_amount: Optional[float]
    fiat_amount: Optional[float]
    fee: Optional[float]
    min_amount: Optional[float]
    max_amount: Optional[float]
    status_code: Optional[int]
    status_label: Optional[str]
    updated_at: Optional[datetime]
    payment_methods: List[str] = []
    remark: Optional[str] = None
    payment_type_ids: List[int] = []


class AccountAds(BaseModel):
    credential_id: str
    account_label: Optional[str]
    exchange: str
    ads: List[AdItem]
    fiat_balance_ads: List[AdItem] = []
    error: Optional[str] = None


class AdsResponse(BaseModel):
    accounts: List[AccountAds]


class AutoPricingPriceGroup(BaseModel):
    min_price: Optional[float]
    max_price: Optional[float]
    competitor_count: int


class AutoPricingAdSummary(BaseModel):
    ad_id: str
    token: Optional[str]
    fiat_currency: Optional[str]
    side: Optional[str]
    price: Optional[float]
    is_auto_enabled: bool
    is_auto_paused: bool
    competitor_groups: List[AutoPricingPriceGroup]
    competitor_groups_full: List[AutoPricingPriceGroup] = []
    spot_symbol: Optional[str] = None
    spot_bid: Optional[float] = None
    spot_ask: Optional[float] = None
    target_price: Optional[float] = None
    guardrail_price: Optional[float] = None
    available_balance: Optional[float] = None
    suggested_buy_qty: Optional[float] = None


class AutoPricingStatusResponse(BaseModel):
    running: bool
    interval_seconds: int
    last_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_error: Optional[str]
    ads: List[AutoPricingAdSummary]
    sell_enabled: Optional[bool] = None
    buy_enabled: Optional[bool] = None


class OrderProcessingStatusResponse(BaseModel):
    running: bool
    interval_seconds: int
    last_run_at: Optional[datetime]
    last_success_at: Optional[datetime]
    last_error: Optional[str]


class AdToggleAutoRequest(BaseModel):
    credential_id: str
    ad_id: str
    enable: bool


class AdToggleAutoResponse(BaseModel):
    remark: str
    response: Dict[str, Any]


class AdOfflineRequest(BaseModel):
    credential_id: str
    ad_id: str


class AdOfflineResponse(BaseModel):
    remark_update: Optional[Dict[str, Any]] = None
    remove_response: Dict[str, Any]


class AdActivateRequest(BaseModel):
    credential_id: str
    ad_id: str


class AdActivateResponse(BaseModel):
    remark: str
    response: Dict[str, Any]


class FiatBalanceLimits(BaseModel):
    minAmount: Optional[str]
    maxAmount: Optional[str]


class FiatBalanceConfig(BaseModel):
    tokens: List[str]
    fiats: List[str]
    limits: Dict[str, List[FiatBalanceLimits]]
    accounts: List[Dict[str, Any]]
    payment_method_id: str = "-1"
    remark_marker: str = FIAT_BALANCE_REMARK_MARKER


class CreateFiatBalanceAdRequest(BaseModel):
    credential_id: str
    tokenId: str
    currencyId: str
    side: str
    price: float
    minAmount: float
    maxAmount: float
    quantity: float
    remark: str = FIAT_BALANCE_REMARK_MARKER
    paymentPeriod: str = "15"


class CreateFiatBalanceBatchRequest(BaseModel):
    credential_id: str
    tokens: List[str]
    fiats: List[str]
    minAmount: Optional[float] = None
    maxAmount: Optional[float] = None
    minAmountMap: Dict[str, float] = {}
    maxAmountMap: Dict[str, float] = {}
    buyQuantity: Optional[float] = None
    sellQuantity: Optional[float] = None
    buyQuantityMap: Dict[str, float] = {}
    sellQuantityMap: Dict[str, float] = {}
    remark: str = FIAT_BALANCE_REMARK_MARKER
    paymentPeriod: str = "15"


class DeleteFiatBalanceAdsRequest(BaseModel):
    credential_id: str
    remark: str = FIAT_BALANCE_REMARK_MARKER
