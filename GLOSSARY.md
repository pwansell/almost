# Almost

Almost is an old reMarkable 2 tablet turned into a framed e-ink display that shows a decorative countdown to upcoming events.

## Language

### The Frame

**Frame**:
The reMarkable tablet once it is mounted and set up as a dedicated display.
_Avoid_: tablet, device, screen, display

**Studio**:
The cloud service that reads the Event Calendar, makes Artwork, and renders Plates for the Frame.
_Avoid_: server, backend, helper, worker

**Plate**:
One finished picture ready for the Frame to show on a given day.
_Avoid_: screen, render, image, frame (lowercase)

**Preview**:
A secret web page from the Studio that shows the coming Plates, rendered fresh each time it is opened.
_Avoid_: dashboard, admin page

**Charge Me Plate**:
The one Plate that the Frame keeps permanently and shows by its own decision when the battery is critically low.
_Avoid_: dead screen, low battery screen

**Countdown**:
What the Frame shows: the whole number of days left until the Featured Event, presented decoratively.
_Avoid_: timer, clock

**Up Next**:
A secondary line under the Countdown naming the Event after the Featured Event and its days remaining.
_Avoid_: then line, subtitle, secondary event

**Event Day**:
The calendar day of the Featured Event, when the Frame shows a special celebratory look instead of a number.
_Avoid_: zero day, today state

**Idle**:
What the Frame shows when there are no upcoming Events.
_Avoid_: blank, empty, none

**Low Battery Mark**:
A small battery symbol in a corner of the Frame, shown only when the battery needs charging soon.
_Avoid_: battery warning, battery indicator

**Offline Mark**:
A small symbol shown when the Frame has not managed to read the Event Calendar for 7 days or more, which means the Countdown may not reflect recent calendar changes.
_Avoid_: no wifi icon, sync warning

**Home Time Zone**:
Melbourne time. All days are counted in it and the Countdown rolls over at Melbourne midnight, wherever an Event takes place.
_Avoid_: local time, device time

### Events

**Event**:
A named day that the Frame counts down to, such as a wedding or a holiday.
_Avoid_: date, occasion, target, deadline

**Featured Event**:
The next upcoming Event, which is the one the Countdown is about. Events on the same day are featured together.
_Avoid_: current event, active event

**Recurring Event**:
An Event that comes back every year on the same date, such as a birthday. Entries that repeat on any other pattern are ignored.
_Avoid_: repeating event, annual event

### Artwork

**Artwork**:
An image suited to the Featured Event, composed as an arch: motifs fill the top and run down the sides, thinning as they descend, and leave open paper in the centre and lower half where the Countdown sits. It is AI-generated if possible, otherwise taken from the Art Library, otherwise the Default Artwork.
_Avoid_: picture, image, background, illustration

**Art Hint**:
Optional words in an Event's description that steer the generated Artwork and double as the Art Library keyword.
_Avoid_: prompt, tag, keyword

**Banner**:
The solid band across the bottom of the Frame that carries the Featured Event's name.
_Avoid_: footer, caption, title bar

**Mat Margin**:
The border on each edge of the screen that the mat hides, kept clear of anything important.
_Avoid_: padding, bezel, safe area

**House Style**:
The single visual style that all generated Artwork is made in: ink and wash, meaning brush ink with soft grey washes in the manner of sumi-e.
_Avoid_: theme, filter, look

**Art Library**:
A curated set of ready-made Artwork, each piece found by a keyword.
_Avoid_: image bank, assets, gallery

**Default Artwork**:
The generic Artwork used when an Event has no generated or library Artwork.
_Avoid_: fallback image, placeholder

**Idle Artwork**:
The single fixed image, with no text, that the Frame shows when Idle.
_Avoid_: screensaver, idle image

**Event Calendar**:
A dedicated, shared Google Calendar. Every entry in it is an Event, and Events come from nowhere else.
_Avoid_: feed, source, schedule, main calendar
