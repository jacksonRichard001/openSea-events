import pytest
from unittest.mock import Mock, AsyncMock, patch
from discord import Client, Embed
from datetime import datetime

from discord_bot import (
    channels_with_events,
    channels_for_event_type,
    color_for,
    create_embed,
    messages_for_events,
    EventType,
)


@pytest.fixture
def mock_event():
    return {
        "event_type": EventType.order,
        "payment": {
            "quantity": "1000000000000000000",
            "decimals": 18,
            "symbol": "ETH",
        },
        "order_type": "listing",
        "expiration_date": int(datetime.now().timestamp()),
        "maker": "0x123...",
        "nft": {
            "name": "Test NFT",
            "opensea_url": "https://opensea.io/test",
        },
    }


@pytest.fixture
def mock_channel_events():
    return [
        ("123", [EventType.listing, EventType.sale]),
        ("456", [EventType.offer, EventType.transfer]),
    ]


def test_channels_with_events(monkeypatch):
    monkeypatch.setenv("DISCORD_EVENTS", "123=listing,sale&456=offer,transfer")
    channels = channels_with_events()
    assert len(channels) == 2
    assert channels[0][0] == "123"
    assert EventType.listing in channels[0][1]
    assert channels[1][0] == "456"
    assert EventType.offer in channels[1][1]


def test_channels_for_event_type(mock_channel_events):
    mock_channels = {"123": Mock(name="channel1"), "456": Mock(name="channel2")}
    
    channels = channels_for_event_type(
        EventType.listing, "listing", mock_channel_events, mock_channels
    )
    assert len(channels) == 1
    assert channels[0] == mock_channels["123"]


def test_color_for():
    assert color_for(EventType.sale, "") == 0x62B778
    assert color_for(EventType.order, "offer") == 0xD63864
    assert color_for(EventType.order, "listing") == 0x66DCF0


@pytest.mark.asyncio
async def test_create_embed(mock_event):
    with patch("discord_bot.username", new_callable=AsyncMock) as mock_username:
        mock_username.return_value = "TestUser"
        embed = await create_embed(mock_event)
        
        assert isinstance(embed, Embed)
        assert "Test NFT" in embed.title
        assert embed.color == color_for(EventType.order, "listing")


@pytest.mark.asyncio
async def test_messages_for_events(mock_event):
    with patch("discord_bot.create_embed", new_callable=AsyncMock) as mock_create_embed:
        mock_embed = Mock()
        mock_create_embed.return_value = mock_embed
        
        messages = await messages_for_events([mock_event])
        assert len(messages) == 1
        assert messages[0]["embeds"] == [mock_embed]


@pytest.mark.asyncio
async def test_message_events_no_discord_events():
    with patch("discord_bot.DISCORD_EVENTS", None):
        result = await message_events([])
        assert result is None 