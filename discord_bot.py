from discord import Client, Embed, Intents
from timeago import format
from typing import List, Tuple, Dict, Any
import os
from datetime import datetime
import asyncio

from opensea import EventType, opensea  # You'll need to convert opensea.ts as well
from util import (
    format_amount,
    image_for_nft,
    log_start,
    username,
)  # Convert util.ts functions

DISCORD_EVENTS = os.getenv("DISCORD_EVENTS")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

ChannelEvents = List[Tuple[str, List[EventType]]]


def channels_with_events() -> ChannelEvents:
    if not DISCORD_EVENTS:
        return []

    channel_list = []
    for channel in DISCORD_EVENTS.split("&"):
        channel_with_events = channel.split("=")
        channel_id = channel_with_events[0]
        event_types = channel_with_events[1].split(",")
        if EventType.listing in event_types or EventType.offer in event_types:
            # Workaround
            event_types.append(EventType.order)
        channel_list.append((channel_id, event_types))

    return channel_list


def channels_for_event_type(
    event_type: EventType,
    order_type: str,
    channel_events: ChannelEvents,
    discord_channels: Dict,
) -> List:
    if event_type == EventType.order:
        event_type = EventType.offer if "offer" in order_type else EventType.listing

    channels = []
    for channel_id, event_types in channel_events:
        if event_type in event_types:
            channel = discord_channels[channel_id]
            channels.append(channel)
    return channels


def color_for(event_type: EventType, order_type: str) -> int:
    # Discord.py uses integer colors instead of hex strings
    if event_type == EventType.order:
        return 0xD63864 if "offer" in order_type else 0x66DCF0
    elif event_type == EventType.sale:
        return 0x62B778
    elif event_type == EventType.cancel:
        return 0x9537B0
    elif event_type == EventType.transfer:
        return 0x5296D5
    else:
        return 0x9537B0


async def create_embed(event: Dict) -> Embed:
    event_type = event.get("event_type")
    payment = event.get("payment")
    from_address = event.get("from_address")
    to_address = event.get("to_address")
    asset = event.get("asset")
    order_type = event.get("order_type")
    expiration_date = event.get("expiration_date")
    maker = event.get("maker")
    buyer = event.get("buyer")
    criteria = event.get("criteria")

    nft = event.get("nft") or asset
    fields = []
    title = ""

    if event_type == EventType.order:
        quantity = payment.get("quantity")
        decimals = payment.get("decimals")
        symbol = payment.get("symbol")
        in_time = format(datetime.fromtimestamp(expiration_date))

        if order_type == "auction":
            title += "Auction:"
            price = format_amount(quantity, decimals, symbol)
            fields.extend(
                [
                    {"name": "Starting Price", "value": price},
                    {"name": "Ends", "value": in_time},
                ]
            )
        elif order_type == "trait_offer":
            trait_type = criteria["trait"]["type"]
            trait_value = criteria["trait"]["value"]
            title += f"Trait offer: {trait_type} -> {trait_value}"
            price = format_amount(quantity, decimals, symbol)
            fields.extend(
                [
                    {"name": "Price", "value": price},
                    {"name": "Expires", "value": in_time},
                ]
            )
        # ... Similar conversions for other order types ...

        fields.append({"name": "By", "value": await username(maker)})

    # ... Similar conversions for other event types ...

    if nft and nft.get("name"):
        title += f" {nft['name']}"

    embed = Embed(title=title, color=color_for(event_type, order_type))

    for field in fields:
        embed.add_field(name=field["name"], value=field["value"], inline=True)

    if nft and nft:
        embed.url = nft.get("opensea_url")
        image = image_for_nft(nft)
        if image:
            embed.set_image(url=image)
    else:
        embed.url = opensea.collection_url()

    return embed


async def messages_for_events(events: List[Dict]) -> List[Dict]:
    messages = []
    for event in events:
        embeds = [await create_embed(event)]
        messages.append({"embeds": embeds})
    return messages


async def message_events(events: List[Dict]):
    if not DISCORD_EVENTS:
        return

    intents = Intents.default()
    client = Client(intents=intents)
    channel_events = channels_with_events()

    # Only handle event types specified by DISCORD_EVENTS
    all_event_types = [et for _, event_types in channel_events for et in event_types]
    filtered_events = [
        event for event in events if event["event_type"] in all_event_types
    ]

    print(f"{log_start}Discord - Relevant events: {len(filtered_events)}")

    if not filtered_events:
        return

    try:
        await client.login(DISCORD_TOKEN)
        discord_channels = {}
        print(f"{log_start}Discord - Selected channels:")

        for channel_id, events in channel_events:
            channel = await client.fetch_channel(channel_id)
            discord_channels[channel_id] = channel
            print(
                f"{log_start}Discord - * #{channel.name or channel.id}: {', '.join(events)}"
            )

        messages = await messages_for_events(filtered_events)

        for index, message in enumerate(messages):
            event = filtered_events[index]
            channels = channels_for_event_type(
                event["event_type"],
                event.get("order_type", ""),
                channel_events,
                discord_channels,
            )

            if not channels:
                continue

            channel_names = [f"#{c.name or c.id}" for c in channels]
            print(
                f"{log_start}Discord - Sending message in {', '.join(channel_names)}: {message['embeds'][0].title}"
            )

            for channel in channels:
                await channel.send(embeds=message["embeds"])

                if index + 1 < len(messages):
                    await asyncio.sleep(3)

    except Exception as error:
        print(f"Error: {error}")
    finally:
        await client.close()
