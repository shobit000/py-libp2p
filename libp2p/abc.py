from abc import (
    ABC,
    abstractmethod,
)
from collections.abc import (
    AsyncIterable,
    Iterable,
    KeysView,
    Sequence,
)
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
)

from multiaddr import (
    Multiaddr,
)
import trio

from libp2p.crypto.keys import (
    KeyPair,
    PrivateKey,
    PublicKey,
)
from libp2p.custom_types import (
    StreamHandlerFn,
    THandler,
    TProtocol,
    ValidatorFn,
)
from libp2p.io.abc import (
    Closer,
    ReadWriteCloser,
)
from libp2p.peer.id import (
    ID,
)
from libp2p.peer.peerinfo import (
    PeerInfo,
)

if TYPE_CHECKING:
    from libp2p.pubsub.pubsub import (
        Pubsub,
    )

from libp2p.pubsub.pb import (
    rpc_pb2,
)
from libp2p.tools.async_service import (
    ServiceAPI,
)

# -------------------------- raw_connection interface.py --------------------------


class IRawConnection(ReadWriteCloser):
    """A Raw Connection provides a Reader and a Writer."""

    is_initiator: bool


# -------------------------- secure_conn interface.py --------------------------


"""
Represents a secured connection object, which includes a connection and details about
the security involved in the secured connection

Relevant go repo: https://github.com/libp2p/go-conn-security/blob/master/interface.go
"""


class AbstractSecureConn(ABC):
    @abstractmethod
    def get_local_peer(self) -> ID:
        pass

    @abstractmethod
    def get_local_private_key(self) -> PrivateKey:
        pass

    @abstractmethod
    def get_remote_peer(self) -> ID:
        pass

    @abstractmethod
    def get_remote_public_key(self) -> PublicKey:
        pass


class ISecureConn(AbstractSecureConn, IRawConnection):
    pass


# -------------------------- stream_muxer abc.py --------------------------


class IMuxedConn(ABC):
    """
    reference: https://github.com/libp2p/go-stream-muxer/blob/master/muxer.go
    """

    peer_id: ID
    event_started: trio.Event

    @abstractmethod
    def __init__(self, conn: ISecureConn, peer_id: ID) -> None:
        """
        Create a new muxed connection.

        :param conn: an instance of secured connection
        for new muxed streams
        :param peer_id: peer_id of peer the connection is to
        """

    @property
    @abstractmethod
    def is_initiator(self) -> bool:
        """If this connection is the initiator."""

    @abstractmethod
    async def start(self) -> None:
        """Start the multiplexer."""

    @abstractmethod
    async def close(self) -> None:
        """Close connection."""

    @property
    @abstractmethod
    def is_closed(self) -> bool:
        """
        Check connection is fully closed.

        :return: true if successful
        """

    @abstractmethod
    async def open_stream(self) -> "IMuxedStream":
        """
        Create a new muxed_stream.

        :return: a new ``IMuxedStream`` stream
        """

    @abstractmethod
    async def accept_stream(self) -> "IMuxedStream":
        """Accept a muxed stream opened by the other end."""


class IMuxedStream(ReadWriteCloser):
    muxed_conn: IMuxedConn

    @abstractmethod
    async def reset(self) -> None:
        """Close both ends of the stream tells this remote side to hang up."""

    @abstractmethod
    def set_deadline(self, ttl: int) -> bool:
        """
        Set deadline for muxed stream.

        :return: a new stream
        """


# -------------------------- net_stream interface.py --------------------------


class INetStream(ReadWriteCloser):
    muxed_conn: IMuxedConn

    @abstractmethod
    def get_protocol(self) -> TProtocol:
        """
        :return: protocol id that stream runs on
        """

    @abstractmethod
    def set_protocol(self, protocol_id: TProtocol) -> None:
        """
        :param protocol_id: protocol id that stream runs on
        """

    @abstractmethod
    async def reset(self) -> None:
        """Close both ends of the stream."""


# -------------------------- net_connection interface.py --------------------------


class INetConn(Closer):
    muxed_conn: IMuxedConn
    event_started: trio.Event

    @abstractmethod
    async def new_stream(self) -> INetStream:
        ...

    @abstractmethod
    def get_streams(self) -> tuple[INetStream, ...]:
        ...


# -------------------------- peermetadata interface.py --------------------------


class IPeerMetadata(ABC):
    @abstractmethod
    def get(self, peer_id: ID, key: str) -> Any:
        """
        :param peer_id: peer ID to lookup key for
        :param key: key to look up
        :return: value at key for given peer
        :raise Exception: peer ID not found
        """

    @abstractmethod
    def put(self, peer_id: ID, key: str, val: Any) -> None:
        """
        :param peer_id: peer ID to lookup key for
        :param key: key to associate with peer
        :param val: value to associated with key
        :raise Exception: unsuccessful put
        """


# -------------------------- addrbook interface.py --------------------------


class IAddrBook(ABC):
    @abstractmethod
    def add_addr(self, peer_id: ID, addr: Multiaddr, ttl: int) -> None:
        """
        Calls add_addrs(peer_id, [addr], ttl)

        :param peer_id: the peer to add address for
        :param addr: multiaddress of the peer
        :param ttl: time-to-live for the address (after this time, address is no longer valid)
        """  # noqa: E501

    @abstractmethod
    def add_addrs(self, peer_id: ID, addrs: Sequence[Multiaddr], ttl: int) -> None:
        """
        Adds addresses for a given peer all with the same time-to-live. If one
        of the addresses already exists for the peer and has a longer TTL, no
        operation should take place. If one of the addresses exists with a
        shorter TTL, extend the TTL to equal param ttl.

        :param peer_id: the peer to add address for
        :param addr: multiaddresses of the peer
        :param ttl: time-to-live for the address (after this time, address is no longer valid
        """  # noqa: E501

    @abstractmethod
    def addrs(self, peer_id: ID) -> list[Multiaddr]:
        """
        :param peer_id: peer to get addresses of
        :return: all known (and valid) addresses for the given peer
        """

    @abstractmethod
    def clear_addrs(self, peer_id: ID) -> None:
        """
        Removes all previously stored addresses.

        :param peer_id: peer to remove addresses of
        """

    @abstractmethod
    def peers_with_addrs(self) -> list[ID]:
        """
        :return: all of the peer IDs stored with addresses
        """


# -------------------------- peerstore interface.py --------------------------


class IPeerStore(IAddrBook, IPeerMetadata):
    @abstractmethod
    def peer_info(self, peer_id: ID) -> PeerInfo:
        """
        :param peer_id: peer ID to get info for
        :return: peer info object
        """

    @abstractmethod
    def get_protocols(self, peer_id: ID) -> list[str]:
        """
        :param peer_id: peer ID to get protocols for
        :return: protocols (as list of strings)
        :raise PeerStoreError: if peer ID not found
        """

    @abstractmethod
    def add_protocols(self, peer_id: ID, protocols: Sequence[str]) -> None:
        """
        :param peer_id: peer ID to add protocols for
        :param protocols: protocols to add
        """

    @abstractmethod
    def set_protocols(self, peer_id: ID, protocols: Sequence[str]) -> None:
        """
        :param peer_id: peer ID to set protocols for
        :param protocols: protocols to set
        """

    @abstractmethod
    def peer_ids(self) -> list[ID]:
        """
        :return: all of the peer IDs stored in peer store
        """

    @abstractmethod
    def get(self, peer_id: ID, key: str) -> Any:
        """
        :param peer_id: peer ID to get peer data for
        :param key: the key to search value for
        :return: value corresponding to the key
        :raise PeerStoreError: if peer ID or value not found
        """

    @abstractmethod
    def put(self, peer_id: ID, key: str, val: Any) -> None:
        """
        :param peer_id: peer ID to put peer data for
        :param key:
        :param value:
        """

    @abstractmethod
    def add_addr(self, peer_id: ID, addr: Multiaddr, ttl: int) -> None:
        """
        :param peer_id: peer ID to add address for
        :param addr:
        :param ttl: time-to-live for the this record
        """

    @abstractmethod
    def add_addrs(self, peer_id: ID, addrs: Sequence[Multiaddr], ttl: int) -> None:
        """
        :param peer_id: peer ID to add address for
        :param addrs:
        :param ttl: time-to-live for the this record
        """

    @abstractmethod
    def addrs(self, peer_id: ID) -> list[Multiaddr]:
        """
        :param peer_id: peer ID to get addrs for
        :return: list of addrs
        """

    @abstractmethod
    def clear_addrs(self, peer_id: ID) -> None:
        """
        :param peer_id: peer ID to clear addrs for
        """

    @abstractmethod
    def peers_with_addrs(self) -> list[ID]:
        """
        :return: all of the peer IDs which has addrs stored in peer store
        """

    @abstractmethod
    def add_pubkey(self, peer_id: ID, pubkey: PublicKey) -> None:
        """
        :param peer_id: peer ID to add public key for
        :param pubkey:
        :raise PeerStoreError: if peer ID already has pubkey set
        """

    @abstractmethod
    def pubkey(self, peer_id: ID) -> PublicKey:
        """
        :param peer_id: peer ID to get public key for
        :return: public key of the peer
        :raise PeerStoreError: if peer ID not found
        """

    @abstractmethod
    def add_privkey(self, peer_id: ID, privkey: PrivateKey) -> None:
        """
        :param peer_id: peer ID to add private key for
        :param privkey:
        :raise PeerStoreError: if peer ID already has privkey set
        """

    @abstractmethod
    def privkey(self, peer_id: ID) -> PrivateKey:
        """
        :param peer_id: peer ID to get private key for
        :return: private key of the peer
        :raise PeerStoreError: if peer ID not found
        """

    @abstractmethod
    def add_key_pair(self, peer_id: ID, key_pair: KeyPair) -> None:
        """
        :param peer_id: peer ID to add private key for
        :param key_pair:
        :raise PeerStoreError: if peer ID already has pubkey or privkey set
        """


# -------------------------- listener interface.py --------------------------


class IListener(ABC):
    @abstractmethod
    async def listen(self, maddr: Multiaddr, nursery: trio.Nursery) -> bool:
        """
        Put listener in listening mode and wait for incoming connections.

        :param maddr: multiaddr of peer
        :return: return True if successful
        """

    @abstractmethod
    def get_addrs(self) -> tuple[Multiaddr, ...]:
        """
        Retrieve list of addresses the listener is listening on.

        :return: return list of addrs
        """

    @abstractmethod
    async def close(self) -> None:
        ...


# -------------------------- network interface.py --------------------------


class INetwork(ABC):
    peerstore: IPeerStore
    connections: dict[ID, INetConn]
    listeners: dict[str, IListener]

    @abstractmethod
    def get_peer_id(self) -> ID:
        """
        :return: the peer id
        """

    @abstractmethod
    async def dial_peer(self, peer_id: ID) -> INetConn:
        """
        dial_peer try to create a connection to peer_id.

        :param peer_id: peer if we want to dial
        :raises SwarmException: raised when an error occurs
        :return: muxed connection
        """

    @abstractmethod
    async def new_stream(self, peer_id: ID) -> INetStream:
        """
        :param peer_id: peer_id of destination
        :param protocol_ids: available protocol ids to use for stream
        :return: net stream instance
        """

    @abstractmethod
    def set_stream_handler(self, stream_handler: StreamHandlerFn) -> None:
        """Set the stream handler for all incoming streams."""

    @abstractmethod
    async def listen(self, *multiaddrs: Sequence[Multiaddr]) -> bool:
        """
        :param multiaddrs: one or many multiaddrs to start listening on
        :return: True if at least one success
        """

    @abstractmethod
    def register_notifee(self, notifee: "INotifee") -> None:
        """
        :param notifee: object implementing Notifee interface
        :return: true if notifee registered successfully, false otherwise
        """

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def close_peer(self, peer_id: ID) -> None:
        pass


class INetworkService(INetwork, ServiceAPI):
    pass


# -------------------------- notifee interface.py --------------------------


class INotifee(ABC):
    @abstractmethod
    async def opened_stream(self, network: "INetwork", stream: INetStream) -> None:
        """
        :param network: network the stream was opened on
        :param stream: stream that was opened
        """

    @abstractmethod
    async def closed_stream(self, network: "INetwork", stream: INetStream) -> None:
        """
        :param network: network the stream was closed on
        :param stream: stream that was closed
        """

    @abstractmethod
    async def connected(self, network: "INetwork", conn: INetConn) -> None:
        """
        :param network: network the connection was opened on
        :param conn: connection that was opened
        """

    @abstractmethod
    async def disconnected(self, network: "INetwork", conn: INetConn) -> None:
        """
        :param network: network the connection was closed on
        :param conn: connection that was closed
        """

    @abstractmethod
    async def listen(self, network: "INetwork", multiaddr: Multiaddr) -> None:
        """
        :param network: network the listener is listening on
        :param multiaddr: multiaddress listener is listening on
        """

    @abstractmethod
    async def listen_close(self, network: "INetwork", multiaddr: Multiaddr) -> None:
        """
        :param network: network the connection was opened on
        :param multiaddr: multiaddress listener is no longer listening on
        """


# -------------------------- host interface.py --------------------------


class IHost(ABC):
    @abstractmethod
    def get_id(self) -> ID:
        """
        :return: peer_id of host
        """

    @abstractmethod
    def get_public_key(self) -> PublicKey:
        """
        :return: the public key belonging to the peer
        """

    @abstractmethod
    def get_private_key(self) -> PrivateKey:
        """
        :return: the private key belonging to the peer
        """

    @abstractmethod
    def get_network(self) -> INetworkService:
        """
        :return: network instance of host
        """

    # FIXME: Replace with correct return type
    @abstractmethod
    def get_mux(self) -> Any:
        """
        :return: mux instance of host
        """

    @abstractmethod
    def get_addrs(self) -> list[Multiaddr]:
        """
        :return: all the multiaddr addresses this host is listening to
        """

    @abstractmethod
    def get_connected_peers(self) -> list[ID]:
        """
        :return: all the ids of peers this host is currently connected to
        """

    @abstractmethod
    def run(self, listen_addrs: Sequence[Multiaddr]) -> AsyncContextManager[None]:
        """
        Run the host instance and listen to ``listen_addrs``.

        :param listen_addrs: a sequence of multiaddrs that we want to listen to
        """

    @abstractmethod
    def set_stream_handler(
        self, protocol_id: TProtocol, stream_handler: StreamHandlerFn
    ) -> None:
        """
        Set stream handler for host.

        :param protocol_id: protocol id used on stream
        :param stream_handler: a stream handler function
        """

    # protocol_id can be a list of protocol_ids
    # stream will decide which protocol_id to run on
    @abstractmethod
    async def new_stream(
        self, peer_id: ID, protocol_ids: Sequence[TProtocol]
    ) -> INetStream:
        """
        :param peer_id: peer_id that host is connecting
        :param protocol_ids: available protocol ids to use for stream
        :return: stream: new stream created
        """

    @abstractmethod
    async def connect(self, peer_info: PeerInfo) -> None:
        """
        Ensure there is a connection between this host and the peer
        with given peer_info.peer_id. connect will absorb the addresses in
        peer_info into its internal peerstore. If there is not an active
        connection, connect will issue a dial, and block until a connection is
        opened, or an error is returned.

        :param peer_info: peer_info of the peer we want to connect to
        :type peer_info: peer.peerinfo.PeerInfo
        """

    @abstractmethod
    async def disconnect(self, peer_id: ID) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


# -------------------------- peerdata interface.py --------------------------


class IPeerData(ABC):
    @abstractmethod
    def get_protocols(self) -> list[str]:
        """
        :return: all protocols associated with given peer
        """

    @abstractmethod
    def add_protocols(self, protocols: Sequence[str]) -> None:
        """
        :param protocols: protocols to add
        """

    @abstractmethod
    def set_protocols(self, protocols: Sequence[str]) -> None:
        """
        :param protocols: protocols to set
        """

    @abstractmethod
    def add_addrs(self, addrs: Sequence[Multiaddr]) -> None:
        """
        :param addrs: multiaddresses to add
        """

    @abstractmethod
    def get_addrs(self) -> list[Multiaddr]:
        """
        :return: all multiaddresses
        """

    @abstractmethod
    def clear_addrs(self) -> None:
        """Clear all addresses."""

    @abstractmethod
    def put_metadata(self, key: str, val: Any) -> None:
        """
        :param key: key in KV pair
        :param val: val to associate with key
        """

    @abstractmethod
    def get_metadata(self, key: str) -> IPeerMetadata:
        """
        :param key: key in KV pair
        :return: val for key
        :raise PeerDataError: key not found
        """

    @abstractmethod
    def add_pubkey(self, pubkey: PublicKey) -> None:
        """
        :param pubkey:
        """

    @abstractmethod
    def get_pubkey(self) -> PublicKey:
        """
        :return: public key of the peer
        :raise PeerDataError: if public key not found
        """

    @abstractmethod
    def add_privkey(self, privkey: PrivateKey) -> None:
        """
        :param privkey:
        """

    @abstractmethod
    def get_privkey(self) -> PrivateKey:
        """
        :return: private key of the peer
        :raise PeerDataError: if private key not found
        """


# ------------------ multiselect_communicator interface.py ------------------


class IMultiselectCommunicator(ABC):
    """
    Communicator helper class that ensures both the client and multistream
    module will follow the same multistream protocol, which is necessary for
    them to work.
    """

    @abstractmethod
    async def write(self, msg_str: str) -> None:
        """
        Write message to stream.

        :param msg_str: message to write
        """

    @abstractmethod
    async def read(self) -> str:
        """Reads message from stream until EOF."""


# -------------------------- multiselect_client interface.py --------------------------


class IMultiselectClient(ABC):
    """
    Client for communicating with receiver's multiselect module in order to
    select a protocol id to communicate over.
    """

    @abstractmethod
    async def handshake(self, communicator: IMultiselectCommunicator) -> None:
        """
        Ensure that the client and multiselect are both using the same
        multiselect protocol.

        :param stream: stream to communicate with multiselect over
        :raise Exception: multiselect protocol ID mismatch
        """

    @abstractmethod
    async def select_one_of(
        self, protocols: Sequence[TProtocol], communicator: IMultiselectCommunicator
    ) -> TProtocol:
        """
        For each protocol, send message to multiselect selecting protocol and
        fail if multiselect does not return same protocol. Returns first
        protocol that multiselect agrees on (i.e. that multiselect selects)

        :param protocol: protocol to select
        :param stream: stream to communicate with multiselect over
        :return: selected protocol
        """

    @abstractmethod
    async def try_select(
        self, communicator: IMultiselectCommunicator, protocol: TProtocol
    ) -> TProtocol:
        """
        Try to select the given protocol or raise exception if fails.

        :param communicator: communicator to use to communicate with counterparty
        :param protocol: protocol to select
        :raise Exception: error in protocol selection
        :return: selected protocol
        """


# -------------------------- multiselect_muxer interface.py --------------------------


class IMultiselectMuxer(ABC):
    """
    Multiselect module that is responsible for responding to a multiselect
    client and deciding on a specific protocol and handler pair to use for
    communication.
    """

    handlers: dict[TProtocol, StreamHandlerFn]

    @abstractmethod
    def add_handler(self, protocol: TProtocol, handler: StreamHandlerFn) -> None:
        """
        Store the handler with the given protocol.

        :param protocol: protocol name
        :param handler: handler function
        """

    def get_protocols(self) -> tuple[TProtocol, ...]:
        return tuple(self.handlers.keys())

    @abstractmethod
    async def negotiate(
        self, communicator: IMultiselectCommunicator
    ) -> tuple[TProtocol, StreamHandlerFn]:
        """
        Negotiate performs protocol selection.

        :param stream: stream to negotiate on
        :return: selected protocol name, handler function
        :raise Exception: negotiation failed exception
        """


# -------------------------- routing interface.py --------------------------


class IContentRouting(ABC):
    @abstractmethod
    def provide(self, cid: bytes, announce: bool = True) -> None:
        """
        Provide adds the given cid to the content routing system.

        If announce is True, it also announces it, otherwise it is just
        kept in the local accounting of which objects are being
        provided.
        """

    @abstractmethod
    def find_provider_iter(self, cid: bytes, count: int) -> Iterable[PeerInfo]:
        """
        Search for peers who are able to provide a given key returns an
        iterator of peer.PeerInfo.
        """


class IPeerRouting(ABC):
    @abstractmethod
    async def find_peer(self, peer_id: ID) -> PeerInfo:
        """
        Find specific Peer FindPeer searches for a peer with given peer_id,
        returns a peer.PeerInfo with relevant addresses.
        """


# -------------------------- security_transport interface.py --------------------------


"""
Transport that is used to secure a connection. This transport is
chosen by a security transport multistream module.

Relevant go repo: https://github.com/libp2p/go-conn-security/blob/master/interface.go
"""


class ISecureTransport(ABC):
    @abstractmethod
    async def secure_inbound(self, conn: IRawConnection) -> ISecureConn:
        """
        Secure the connection, either locally or by communicating with opposing
        node via conn, for an inbound connection (i.e. we are not the
        initiator)

        :return: secure connection object (that implements secure_conn_interface)
        """

    @abstractmethod
    async def secure_outbound(self, conn: IRawConnection, peer_id: ID) -> ISecureConn:
        """
        Secure the connection, either locally or by communicating with opposing
        node via conn, for an inbound connection (i.e. we are the initiator)

        :return: secure connection object (that implements secure_conn_interface)
        """


# -------------------------- transport interface.py --------------------------


class ITransport(ABC):
    @abstractmethod
    async def dial(self, maddr: Multiaddr) -> IRawConnection:
        """
        Dial a transport to peer listening on multiaddr.

        :param multiaddr: multiaddr of peer
        :param self_id: peer_id of the dialer (to send to receiver)
        :return: list of multiaddrs
        """

    @abstractmethod
    def create_listener(self, handler_function: THandler) -> IListener:
        """
        Create listener on transport.

        :param handler_function: a function called when a new conntion is received
            that takes a connection as argument which implements interface-connection
        :return: a listener object that implements listener_interface.py
        """


# -------------------------- pubsub abc.py --------------------------


class ISubscriptionAPI(
    AsyncContextManager["ISubscriptionAPI"], AsyncIterable[rpc_pb2.Message]
):
    @abstractmethod
    async def unsubscribe(self) -> None:
        ...

    @abstractmethod
    async def get(self) -> rpc_pb2.Message:
        ...


class IPubsubRouter(ABC):
    @abstractmethod
    def get_protocols(self) -> list[TProtocol]:
        """
        :return: the list of protocols supported by the router
        """

    @abstractmethod
    def attach(self, pubsub: "Pubsub") -> None:
        """
        Attach is invoked by the PubSub constructor to attach the router to a
        freshly initialized PubSub instance.

        :param pubsub: pubsub instance to attach to
        """

    @abstractmethod
    def add_peer(self, peer_id: ID, protocol_id: TProtocol) -> None:
        """
        Notifies the router that a new peer has been connected.

        :param peer_id: id of peer to add
        :param protocol_id: router protocol the peer speaks, e.g., floodsub, gossipsub
        """

    @abstractmethod
    def remove_peer(self, peer_id: ID) -> None:
        """
        Notifies the router that a peer has been disconnected.

        :param peer_id: id of peer to remove
        """

    @abstractmethod
    async def handle_rpc(self, rpc: rpc_pb2.RPC, sender_peer_id: ID) -> None:
        """
        Invoked to process control messages in the RPC envelope.
        It is invoked after subscriptions and payload messages have been processed

        :param rpc: RPC message
        :param sender_peer_id: id of the peer who sent the message
        """

    @abstractmethod
    async def publish(self, msg_forwarder: ID, pubsub_msg: rpc_pb2.Message) -> None:
        """
        Invoked to forward a new message that has been validated.

        :param msg_forwarder: peer_id of message sender
        :param pubsub_msg: pubsub message to forward
        """

    @abstractmethod
    async def join(self, topic: str) -> None:
        """
        Join notifies the router that we want to receive and forward messages
        in a topic. It is invoked after the subscription announcement.

        :param topic: topic to join
        """

    @abstractmethod
    async def leave(self, topic: str) -> None:
        """
        Leave notifies the router that we are no longer interested in a topic.
        It is invoked after the unsubscription announcement.

        :param topic: topic to leave
        """


class IPubsub(ServiceAPI):
    @property
    @abstractmethod
    def my_id(self) -> ID:
        ...

    @property
    @abstractmethod
    def protocols(self) -> tuple[TProtocol, ...]:
        ...

    @property
    @abstractmethod
    def topic_ids(self) -> KeysView[str]:
        ...

    @abstractmethod
    def set_topic_validator(
        self, topic: str, validator: ValidatorFn, is_async_validator: bool
    ) -> None:
        ...

    @abstractmethod
    def remove_topic_validator(self, topic: str) -> None:
        ...

    @abstractmethod
    async def wait_until_ready(self) -> None:
        ...

    @abstractmethod
    async def subscribe(self, topic_id: str) -> ISubscriptionAPI:
        ...

    @abstractmethod
    async def unsubscribe(self, topic_id: str) -> None:
        ...

    @abstractmethod
    async def publish(self, topic_id: str, data: bytes) -> None:
        ...
