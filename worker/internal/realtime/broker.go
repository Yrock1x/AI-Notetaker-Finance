// Package realtime is the worker's in-process pub/sub for live-meeting fan-out.
// It ports app/realtime/pubsub.py: a single-process, per-topic set of subscriber
// channels. Webhook handlers publish events; each SSE connection subscribes to a
// meeting topic and streams them out. This is stdlib-only (no external broker),
// which is sufficient because the worker runs as a single process — the same
// constraint the Python module documents. If the worker is ever horizontally
// scaled this package is the one place that must grow a real broker.
//
// A cross-package singleton (Default) backs the SSE + webhook handlers because
// the Server struct may not be edited to carry a *Broker field; the broker is
// process-global state with no per-request configuration, so a singleton is the
// clean equivalent of the Python module-level `pubsub`.
package realtime

import "sync"

// DefaultMaxSize bounds each subscriber's buffer so a slow/stalled SSE consumer
// can't grow its channel without limit. On overflow Publish drops the event for
// that subscriber rather than blocking the publisher (which would stall the
// webhook ingest path for everyone). Mirrors pubsub.DEFAULT_MAXSIZE.
const DefaultMaxSize = 1000

// Event is one fan-out message: {"kind", "payload"} (matches publish_meeting_event).
type Event struct {
	Kind    string         `json:"kind"`
	Payload map[string]any `json:"payload"`
}

// MeetingTopic is the topic string for a meeting (ports meeting_topic).
func MeetingTopic(meetingID string) string { return "meeting:" + meetingID }

// Subscription is a single subscriber's handle: a receive-only channel of events
// plus the topic it is registered under (so Unsubscribe is O(1) for the caller).
type Subscription struct {
	C     <-chan Event
	ch    chan Event
	topic string
}

// Broker is an in-process pub/sub keyed by topic string (ports PubSub).
type Broker struct {
	maxsize int
	mu      sync.Mutex
	subs    map[string]map[*Subscription]struct{}
}

// NewBroker returns a broker whose subscriber channels buffer maxsize events.
func NewBroker(maxsize int) *Broker {
	if maxsize <= 0 {
		maxsize = DefaultMaxSize
	}
	return &Broker{maxsize: maxsize, subs: make(map[string]map[*Subscription]struct{})}
}

// Default is the process-global broker shared by the SSE endpoint and the Recall
// webhook handler, mirroring the module-level `pubsub` singleton in Python.
var Default = NewBroker(DefaultMaxSize)

// Subscribe registers and returns a new subscription that receives events for
// topic (ports PubSub.subscribe). Always pair with Unsubscribe.
func (b *Broker) Subscribe(topic string) *Subscription {
	ch := make(chan Event, b.maxsize)
	s := &Subscription{C: ch, ch: ch, topic: topic}
	b.mu.Lock()
	set := b.subs[topic]
	if set == nil {
		set = make(map[*Subscription]struct{})
		b.subs[topic] = set
	}
	set[s] = struct{}{}
	b.mu.Unlock()
	return s
}

// Unsubscribe removes sub from its topic (no-op if already gone). Ports
// PubSub.unsubscribe.
func (b *Broker) Unsubscribe(sub *Subscription) {
	if sub == nil {
		return
	}
	b.mu.Lock()
	if set := b.subs[sub.topic]; set != nil {
		delete(set, sub)
		if len(set) == 0 {
			delete(b.subs, sub.topic)
		}
	}
	b.mu.Unlock()
}

// Publish delivers event to every subscriber of topic (ports PubSub.publish).
// Non-blocking send with drop-on-full: a subscriber whose buffer is full silently
// loses the event so a single slow consumer never blocks the publisher or peers.
func (b *Broker) Publish(topic string, event Event) {
	b.mu.Lock()
	subs := make([]*Subscription, 0, len(b.subs[topic]))
	for s := range b.subs[topic] {
		subs = append(subs, s)
	}
	b.mu.Unlock()
	for _, s := range subs {
		select {
		case s.ch <- event:
		default: // buffer full — drop for this subscriber
		}
	}
}

// PublishMeetingEvent fans a {kind, payload} event out to a meeting's topic
// (ports publish_meeting_event). kind is one of: transcript_segment,
// participant, chat, meeting, bot_session.
func (b *Broker) PublishMeetingEvent(meetingID, kind string, payload map[string]any) {
	b.Publish(MeetingTopic(meetingID), Event{Kind: kind, Payload: payload})
}

// SubscriberCount reports how many subscribers watch topic (ports subscriber_count).
func (b *Broker) SubscriberCount(topic string) int {
	b.mu.Lock()
	defer b.mu.Unlock()
	return len(b.subs[topic])
}
