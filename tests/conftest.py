"""Pytest configuration and mocks for testing Renault / My Dacia custom integration."""

from __future__ import annotations

import sys
from types import ModuleType
import typing
from typing import Any
from unittest.mock import MagicMock

if not hasattr(typing, "override"):
    setattr(typing, "override", lambda f: f)


def _ensure_mock_modules() -> None:
    """Mock external libraries if not already installed in the environment."""
    if "homeassistant" not in sys.modules:
        ha = ModuleType("homeassistant")
        ha.__path__ = []

        ha_const = ModuleType("homeassistant.const")
        ha_const.Platform = MagicMock()
        ha_const.Platform.BINARY_SENSOR = "binary_sensor"
        ha_const.Platform.BUTTON = "button"
        ha_const.Platform.CLIMATE = "climate"
        ha_const.Platform.DEVICE_TRACKER = "device_tracker"
        ha_const.Platform.NUMBER = "number"
        ha_const.Platform.SELECT = "select"
        ha_const.Platform.SENSOR = "sensor"
        ha_const.Platform.SWITCH = "switch"
        ha_const.Platform.TIME = "time"
        ha_const.EntityCategory = MagicMock()
        ha_const.EntityCategory.CONFIG = "config"
        ha_const.EntityCategory.DIAGNOSTIC = "diagnostic"
        ha_const.UnitOfTemperature = MagicMock()
        ha_const.UnitOfTemperature.CELSIUS = "°C"
        ha_const.UnitOfTime = MagicMock()
        ha_const.UnitOfTime.MINUTES = "min"
        ha_const.PERCENTAGE = "%"
        ha_const.ATTR_TEMPERATURE = "temperature"
        ha_const.CONF_CODE = "code"
        ha_const.CONF_EMAIL = "email"

        ha_core = ModuleType("homeassistant.core")
        ha_core.HomeAssistant = MagicMock
        ha_core.callback = lambda f: f
        ha_core.ServiceCall = MagicMock

        ha_exceptions = ModuleType("homeassistant.exceptions")
        class HomeAssistantError(Exception): pass
        class ServiceValidationError(HomeAssistantError): pass
        class ConfigEntryAuthFailed(HomeAssistantError): pass
        class ConfigEntryError(HomeAssistantError): pass
        class ConfigEntryNotReady(HomeAssistantError): pass
        ha_exceptions.HomeAssistantError = HomeAssistantError
        ha_exceptions.ServiceValidationError = ServiceValidationError
        ha_exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed
        ha_exceptions.ConfigEntryError = ConfigEntryError
        ha_exceptions.ConfigEntryNotReady = ConfigEntryNotReady

        ha_helpers = ModuleType("homeassistant.helpers")
        ha_helpers.__path__ = []
        ha_helpers_entity = ModuleType("homeassistant.helpers.entity")
        class Entity:
            _attr_has_entity_name = True
            _attr_device_info = None
            _attr_unique_id = None
            def __init__(self, *args, **kwargs):
                pass
            @property
            def unique_id(self):
                return self._attr_unique_id
            def async_write_ha_state(self):
                pass


        from dataclasses import dataclass
        @dataclass(frozen=True, kw_only=True)
        class EntityDescription:
            key: str
            name: str | None = None
            translation_key: str | None = None
            icon: str | None = None
            device_class: Any = None
            entity_category: Any = None
            has_entity_name: bool = False

        ha_helpers_entity.Entity = Entity
        ha_helpers_entity.EntityDescription = EntityDescription
        ha_helpers_update = ModuleType("homeassistant.helpers.update_coordinator")
        class DataUpdateCoordinator:
            __class_getitem__ = classmethod(lambda cls, item: cls)
            def __init__(self, *args, **kwargs):
                self.data = kwargs.get("data")
                self.update_method = kwargs.get("update_method")
                self.assumed_state = False

        class UpdateFailed(HomeAssistantError):
            def __init__(self, *args, **kwargs):
                super().__init__(*args)
                self.kwargs = kwargs
        class CoordinatorEntity:

            __class_getitem__ = classmethod(lambda cls, item: cls)
            def __init__(self, coordinator):
                self.coordinator = coordinator
        ha_helpers_update.DataUpdateCoordinator = DataUpdateCoordinator
        ha_helpers_update.UpdateFailed = UpdateFailed
        ha_helpers_update.CoordinatorEntity = CoordinatorEntity

        ha_config_entries = ModuleType("homeassistant.config_entries")
        class ConfigEntry(MagicMock):
            __class_getitem__ = classmethod(lambda cls, item: cls)
        ha_config_entries.ConfigEntry = ConfigEntry
        ha_config_entries.SOURCE_REAUTH = "reauth"
        ha_config_entries.SOURCE_RECONFIGURE = "reconfigure"

        ha_cv = ModuleType("homeassistant.helpers.config_validation")
        ha_cv.config_entry_only_config_schema = lambda domain: MagicMock()
        ha_cv.string = str
        ha_cv.boolean = bool
        ha_cv.positive_int = int
        ha_cv.positive_float = float
        ha_cv.datetime = MagicMock()

        ha_dr = ModuleType("homeassistant.helpers.device_registry")
        ha_dr.DeviceInfo = MagicMock

        ha_ir = ModuleType("homeassistant.helpers.issue_registry")
        ha_ir.async_create_issue = MagicMock()
        ha_ir.async_delete_issue = MagicMock()
        ha_ir.IssueSeverity = MagicMock()

        ha_typing = ModuleType("homeassistant.helpers.typing")
        ha_typing.ConfigType = dict

        ha_service = ModuleType("homeassistant.helpers.service")
        ha_service.async_get_device_and_config_entry = MagicMock()

        sys.modules["homeassistant"] = ha
        sys.modules["homeassistant.const"] = ha_const
        ha_core.CALLBACK_TYPE = Any
        sys.modules["homeassistant.core"] = ha_core

        ha_aiohttp = ModuleType("homeassistant.helpers.aiohttp_client")
        ha_aiohttp.async_get_clientsession = MagicMock()
        sys.modules["homeassistant.helpers.aiohttp_client"] = ha_aiohttp
        sys.modules["homeassistant.exceptions"] = ha_exceptions
        sys.modules["homeassistant.helpers"] = ha_helpers
        sys.modules["homeassistant.helpers.entity"] = ha_helpers_entity
        sys.modules["homeassistant.helpers.update_coordinator"] = ha_helpers_update
        sys.modules["homeassistant.config_entries"] = ha_config_entries
        sys.modules["homeassistant.helpers.config_validation"] = ha_cv
        sys.modules["homeassistant.helpers.device_registry"] = ha_dr
        sys.modules["homeassistant.helpers.issue_registry"] = ha_ir
        sys.modules["homeassistant.helpers.typing"] = ha_typing
        sys.modules["homeassistant.helpers.service"] = ha_service

        ha_ep = ModuleType("homeassistant.helpers.entity_platform")
        ha_ep.AddConfigEntryEntitiesCallback = Any
        sys.modules["homeassistant.helpers.entity_platform"] = ha_ep

        ha_climate = ModuleType("homeassistant.components.climate")
        ha_climate.ClimateEntity = ha_helpers_entity.Entity
        ha_climate.ClimateEntityFeature = MagicMock()
        ha_climate.HVACMode = MagicMock()
        ha_climate.HVACAction = MagicMock()
        sys.modules["homeassistant.components.climate"] = ha_climate

        ha_switch = ModuleType("homeassistant.components.switch")
        ha_switch.SwitchEntity = ha_helpers_entity.Entity
        ha_switch.SwitchDeviceClass = MagicMock()
        sys.modules["homeassistant.components.switch"] = ha_switch

        ha_time = ModuleType("homeassistant.components.time")
        ha_time.TimeEntity = ha_helpers_entity.Entity
        sys.modules["homeassistant.components.time"] = ha_time

        ha_number = ModuleType("homeassistant.components.number")
        ha_number.NumberEntity = ha_helpers_entity.Entity
        ha_number.NumberDeviceClass = MagicMock()
        sys.modules["homeassistant.components.number"] = ha_number

        ha_select = ModuleType("homeassistant.components.select")
        ha_select.SelectEntity = ha_helpers_entity.Entity
        sys.modules["homeassistant.components.select"] = ha_select

        ha_sensor = ModuleType("homeassistant.components.sensor")
        ha_sensor.SensorEntity = ha_helpers_entity.Entity
        ha_sensor.SensorDeviceClass = MagicMock()
        ha_sensor.SensorStateClass = MagicMock()
        sys.modules["homeassistant.components.sensor"] = ha_sensor

        ha_button = ModuleType("homeassistant.components.button")
        ha_button.ButtonEntity = ha_helpers_entity.Entity
        ha_button.ButtonDeviceClass = MagicMock()
        sys.modules["homeassistant.components.button"] = ha_button

        ha_binary = ModuleType("homeassistant.components.binary_sensor")
        ha_binary.BinarySensorEntity = ha_helpers_entity.Entity
        ha_binary.BinarySensorDeviceClass = MagicMock()
        sys.modules["homeassistant.components.binary_sensor"] = ha_binary

    if "renault_api" not in sys.modules:
        ra = ModuleType("renault_api")
        ra.__path__ = []

        ra_kam = ModuleType("renault_api.kamereon")
        ra_kam.__path__ = []
        ra_models = ModuleType("renault_api.kamereon.models")
        ra_models.__path__ = []
        ra_kam_exc = ModuleType("renault_api.kamereon.exceptions")

        class ForbiddenException(Exception): pass
        class NotAuthenticatedException(Exception): pass
        class NotSupportedException(Exception): pass
        class QuotaLimitException(Exception): pass
        class KamereonResponseException(Exception): pass
        class RenaultException(Exception): pass

        class AccessDeniedException(Exception): pass
        ra_kam_exc.ForbiddenException = ForbiddenException
        ra_kam_exc.AccessDeniedException = AccessDeniedException
        ra_kam_exc.NotSupportedException = NotSupportedException
        ra_kam_exc.QuotaLimitException = QuotaLimitException
        ra_kam_exc.KamereonResponseException = KamereonResponseException

        ra_exc = ModuleType("renault_api.exceptions")
        ra_exc.NotAuthenticatedException = NotAuthenticatedException
        ra_exc.NotSupportedException = NotSupportedException
        ra_exc.QuotaLimitException = QuotaLimitException
        ra_exc.KamereonResponseException = KamereonResponseException
        ra_exc.RenaultException = RenaultException

        class EndpointDefinition:
            def __init__(self, url: str, mode: str | None = None):
                self.url = url
                self.mode = mode

        class KamereonVehicleDataAttributes:
            def __init__(self, raw_data=None):
                self.raw_data = raw_data or {}

        ra_models.EndpointDefinition = EndpointDefinition
        ra_models.KamereonVehicleDataAttributes = KamereonVehicleDataAttributes
        ra_models._DEFAULT_ENDPOINTS = {
            "actions/horn-start": EndpointDefinition("/horn"),
            "actions/hvac-start": EndpointDefinition("/hvac-start"),
            "actions/lights-start": EndpointDefinition("/lights"),
            "actions/refresh-location": EndpointDefinition("/refresh-location"),
            "battery-status": EndpointDefinition("/battery-status"),
            "charges": EndpointDefinition("/charges"),
            "cockpit": EndpointDefinition("/cockpit"),
            "hvac-status": EndpointDefinition("/hvac-status"),
            "location": EndpointDefinition("/location"),
        }
        ra_models._KCA_ALTERNATIVE_ENDPOINTS = {
            "actions/hvac-stop": EndpointDefinition("/hvac-stop")
        }
        ra_models._VEHICLE_ENDPOINTS = {}

        class KamereonVehicleBatterySocData(KamereonVehicleDataAttributes):
            socMin: int | None = None
            socTarget: int | None = None
            @classmethod
            def from_dict(cls, d):
                obj = cls(raw_data=d)
                obj.socMin = d.get("socMin")
                obj.socTarget = d.get("socTarget")
                return obj

        ra_models.KamereonVehicleBatterySocData = KamereonVehicleBatterySocData

        ra_gigya = ModuleType("renault_api.gigya")
        ra_gigya.__path__ = []
        ra_gigya.GIGYA_JWT = "gigya-jwt"
        ra_gigya_exc = ModuleType("renault_api.gigya.exceptions")
        class GigyaException(Exception): pass
        class InvalidVerificationCodeException(GigyaException): pass
        class PendingTwoFactorAuthenticationException(GigyaException): pass
        class InvalidCredentialsException(GigyaException): pass
        ra_gigya_exc.GigyaException = GigyaException
        ra_gigya_exc.InvalidVerificationCodeException = InvalidVerificationCodeException
        ra_gigya_exc.PendingTwoFactorAuthenticationException = PendingTwoFactorAuthenticationException
        ra_gigya_exc.InvalidCredentialsException = InvalidCredentialsException

        ra_gigya_models = ModuleType("renault_api.gigya.models")
        class GigyaTfaEmail: pass
        ra_gigya_models.GigyaTfaEmail = GigyaTfaEmail

        ra_account = ModuleType("renault_api.renault_account")
        class RenaultAccount: pass
        ra_account.RenaultAccount = RenaultAccount

        ra_client = ModuleType("renault_api.renault_client")
        class RenaultClient: pass
        ra_client.RenaultClient = RenaultClient

        class KamereonVehiclesLink: pass
        ra_models.KamereonVehiclesLink = KamereonVehiclesLink

        sys.modules["renault_api.gigya.models"] = ra_gigya_models
        sys.modules["renault_api.renault_account"] = ra_account
        sys.modules["renault_api.renault_client"] = ra_client

        ra_vehicle = ModuleType("renault_api.renault_vehicle")
        class RenaultVehicle: pass
        ra_vehicle.RenaultVehicle = RenaultVehicle
        sys.modules["renault_api.renault_vehicle"] = ra_vehicle

        ra_cred = ModuleType("renault_api.credential")
        class Credential:
            def __init__(self, value): self.value = value
        class JWTCredential(Credential):
            def get_claims(self): return {}
        ra_cred.Credential = Credential
        ra_cred.JWTCredential = JWTCredential

        ra_const = ModuleType("renault_api.const")
        ra_const.AVAILABLE_LOCALES = {"de_DE": "Germany"}
        ra_const.CONF_KAMEREON_APIKEY = "kamereon_apikey"

        ra_schemas = ModuleType("renault_api.kamereon.schemas")
        class KamereonResponseSchema:
            @classmethod
            def loads(cls, data):
                return MagicMock()
        ra_schemas.KamereonResponseSchema = KamereonResponseSchema
        ra_kam.schemas = ra_schemas
        ra_kam.models = ra_models

        sys.modules["renault_api"] = ra
        sys.modules["renault_api.exceptions"] = ra_exc
        sys.modules["renault_api.kamereon"] = ra_kam
        sys.modules["renault_api.kamereon.models"] = ra_models
        sys.modules["renault_api.kamereon.schemas"] = ra_schemas
        sys.modules["renault_api.kamereon.exceptions"] = ra_kam_exc
        sys.modules["renault_api.gigya"] = ra_gigya
        sys.modules["renault_api.gigya.exceptions"] = ra_gigya_exc
        sys.modules["renault_api.credential"] = ra_cred
        sys.modules["renault_api.const"] = ra_const

    if "marshmallow" not in sys.modules:
        mm = ModuleType("marshmallow")
        mm.__path__ = []
        mm_schema = ModuleType("marshmallow.schema")
        class Schema: pass
        mm_schema.Schema = Schema
        sys.modules["marshmallow"] = mm
        sys.modules["marshmallow.schema"] = mm_schema

    if "probatio" not in sys.modules:
        prob = ModuleType("probatio")
        class Schema(dict):
            def extend(self, d):
                return Schema({**self, **d})
        prob.Schema = Schema
        prob.Required = lambda k: k
        prob.Optional = lambda k, **kw: k
        prob.Any = lambda *args: MagicMock()
        prob.All = lambda *args: MagicMock()
        prob.In = lambda *args: MagicMock()
        prob.EnsureList = lambda *args: MagicMock()
        sys.modules["probatio"] = prob


_ensure_mock_modules()
