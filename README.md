# Fix: Remove unused `context` parameter from `importEventAsSchedule`

## Issue

The `importEventAsSchedule(event:context:)` method in `CalendarSyncService.swift` had an unused `context: Any` parameter that forced unnecessary dependencies on callers without being used in the implementation.

## Solution

Removed the unused `context: Any` parameter from the function signature:

### Before
```swift
func importEventAsSchedule(event: ExternalCalendarEvent, context: Any) -> ScheduleItem {
    ScheduleItem(
        title: "📅 \(event.title)",
        detail: [event.calendarName, event.notes].compactMap { $0 }.joined(separator: "\n"),
        startDate: event.startDate,
        endDate: event.endDate,
        isAllDay: event.isAllDay,
        priority: .normal,
        location: event.location ?? ""
    )
}
```

### After
```swift
func importEventAsSchedule(event: ExternalCalendarEvent) -> ScheduleItem {
    ScheduleItem(
        title: "📅 \(event.title)",
        detail: [event.calendarName, event.notes].compactMap { $0 }.joined(separator: "\n"),
        startDate: event.startDate,
        endDate: event.endDate,
        isAllDay: event.isAllDay,
        priority: .normal,
        location: event.location ?? ""
    )
}
```

## Benefits

1. **Cleaner API**: Removes unnecessary parameter that was never used
2. **Fewer dependencies**: Callers no longer need to pass a context object
3. **Better type safety**: If context is needed in the future, it should be properly typed (e.g., `ModelContext`) rather than `Any`

## File Changed

- `AISecretary/AISecretary/Services/CalendarSyncService.swift` (line 173)

## Reference

Original issue: https://github.com/mitsu888/cline/pull/2#discussion_r3068620803
