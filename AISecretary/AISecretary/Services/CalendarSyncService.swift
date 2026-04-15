import Foundation
import EventKit
import Combine

/// カレンダー同期サービス
/// Apple Calendar (EventKit) を通じて Google Calendar / Apple Calendar と連携
/// Google CalendarはiOSのカレンダーアカウント設定経由で自動同期される
final class CalendarSyncService: ObservableObject {
    static let shared = CalendarSyncService()

    private let eventStore = EKEventStore()

    @Published var authorizationStatus: EKAuthorizationStatus = .notDetermined
    @Published var availableCalendars: [CalendarInfo] = []
    @Published var selectedCalendarIDs: Set<String> = [] {
        didSet {
            let array = Array(selectedCalendarIDs)
            UserDefaults.standard.set(array, forKey: "selected_calendar_ids")
        }
    }
    @Published var isSyncing = false
    @Published var lastSyncDate: Date?
    @Published var syncedEvents: [ExternalCalendarEvent] = []
    @Published var autoSyncEnabled: Bool {
        didSet {
            UserDefaults.standard.set(autoSyncEnabled, forKey: "calendar_auto_sync")
        }
    }

    private var syncTimer: Timer?

    private init() {
        self.autoSyncEnabled = UserDefaults.standard.bool(forKey: "calendar_auto_sync")

        if let savedIDs = UserDefaults.standard.stringArray(forKey: "selected_calendar_ids") {
            self.selectedCalendarIDs = Set(savedIDs)
        }

        if let lastSync = UserDefaults.standard.object(forKey: "calendar_last_sync") as? Date {
            self.lastSyncDate = lastSync
        }

        checkAuthorization()
    }

    // MARK: - 権限管理

    /// カレンダーアクセス権限を確認
    func checkAuthorization() {
        authorizationStatus = EKEventStore.authorizationStatus(for: .event)
    }

    /// カレンダーアクセス権限をリクエスト
    func requestAccess() async -> Bool {
        do {
            let granted = try await eventStore.requestFullAccessToEvents()
            await MainActor.run {
                authorizationStatus = granted ? .fullAccess : .denied
                if granted {
                    loadAvailableCalendars()
                }
            }
            return granted
        } catch {
            await MainActor.run {
                authorizationStatus = .denied
            }
            return false
        }
    }

    // MARK: - カレンダー一覧

    /// 利用可能なカレンダー一覧を取得
    func loadAvailableCalendars() {
        let calendars = eventStore.calendars(for: .event)
        availableCalendars = calendars.map { calendar in
            CalendarInfo(
                id: calendar.calendarIdentifier,
                title: calendar.title,
                sourceName: calendar.source.title,
                sourceType: mapSourceType(calendar.source.sourceType),
                color: calendar.cgColor
            )
        }.sorted { $0.sourceName < $1.sourceName }
    }

    /// カレンダーの選択を切り替え
    func toggleCalendar(_ calendarID: String) {
        if selectedCalendarIDs.contains(calendarID) {
            selectedCalendarIDs.remove(calendarID)
        } else {
            selectedCalendarIDs.insert(calendarID)
        }
    }

    // MARK: - イベント同期

    /// 選択されたカレンダーからイベントを取得
    func syncEvents(from startDate: Date, to endDate: Date) async {
        guard authorizationStatus == .fullAccess else { return }

        await MainActor.run { isSyncing = true }

        let calendars = eventStore.calendars(for: .event).filter {
            selectedCalendarIDs.contains($0.calendarIdentifier)
        }

        guard !calendars.isEmpty else {
            await MainActor.run {
                isSyncing = false
                syncedEvents = []
            }
            return
        }

        let predicate = eventStore.predicateForEvents(
            withStart: startDate,
            end: endDate,
            calendars: calendars
        )

        let ekEvents = eventStore.events(matching: predicate)

        let events = ekEvents.map { event in
            ExternalCalendarEvent(
                id: event.eventIdentifier,
                title: event.title ?? "（無題）",
                startDate: event.startDate,
                endDate: event.endDate,
                isAllDay: event.isAllDay,
                location: event.location,
                calendarName: event.calendar.title,
                calendarSourceType: mapSourceType(event.calendar.source.sourceType),
                notes: event.notes
            )
        }.sorted { $0.startDate < $1.startDate }

        await MainActor.run {
            syncedEvents = events
            isSyncing = false
            lastSyncDate = Date()
            UserDefaults.standard.set(Date(), forKey: "calendar_last_sync")
        }
    }

    /// 今日のイベントを同期
    func syncTodayEvents() async {
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: Date())
        let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) ?? startOfDay
        await syncEvents(from: startOfDay, to: endOfDay)
    }

    /// 指定日のイベントを同期
    func syncEventsForDate(_ date: Date) async {
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: date)
        let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) ?? startOfDay
        await syncEvents(from: startOfDay, to: endOfDay)
    }

    /// 1週間分のイベントを同期
    func syncWeekEvents() async {
        let startOfDay = Calendar.current.startOfDay(for: Date())
        let endOfWeek = Calendar.current.date(byAdding: .day, value: 7, to: startOfDay) ?? startOfDay
        await syncEvents(from: startOfDay, to: endOfWeek)
    }

    // MARK: - アプリ内スケジュールへエクスポート

    /// 外部カレンダーイベントをアプリ内ScheduleItemに変換
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

    // MARK: - アプリ内スケジュールをカレンダーへエクスポート

    /// ScheduleItemを外部カレンダーに書き出し
    func exportScheduleToCalendar(_ schedule: ScheduleItem, calendarID: String) -> Bool {
        guard authorizationStatus == .fullAccess else { return false }

        guard let calendar = eventStore.calendars(for: .event)
            .first(where: { $0.calendarIdentifier == calendarID }) else { return false }

        let event = EKEvent(eventStore: eventStore)
        event.title = schedule.title
        event.notes = schedule.detail
        event.startDate = schedule.startDate
        event.endDate = schedule.endDate
        event.isAllDay = schedule.isAllDay
        event.location = schedule.location
        event.calendar = calendar

        if let reminderMinutes = schedule.reminderMinutesBefore {
            event.addAlarm(EKAlarm(relativeOffset: TimeInterval(-reminderMinutes * 60)))
        }

        do {
            try eventStore.save(event, span: .thisEvent)
            return true
        } catch {
            return false
        }
    }

    // MARK: - 自動同期

    /// 自動同期を開始
    func startAutoSync() {
        stopAutoSync()
        guard autoSyncEnabled else { return }

        syncTimer = Timer.scheduledTimer(withTimeInterval: 300, repeats: true) { [weak self] _ in
            Task {
                await self?.syncWeekEvents()
            }
        }
        // 初回即時実行
        Task { await syncWeekEvents() }
    }

    /// 自動同期を停止
    func stopAutoSync() {
        syncTimer?.invalidate()
        syncTimer = nil
    }

    // MARK: - Private

    private func mapSourceType(_ sourceType: EKSourceType) -> CalendarSourceType {
        switch sourceType {
        case .local: .local
        case .exchange: .exchange
        case .calDAV: .calDAV    // Google Calendar / iCloud
        case .subscribed: .subscribed
        case .birthdays: .birthdays
        @unknown default: .local
        }
    }
}

// MARK: - Data Types

struct CalendarInfo: Identifiable {
    let id: String
    let title: String
    let sourceName: String
    let sourceType: CalendarSourceType
    let color: CGColor?

    var sourceIcon: String {
        sourceType.icon
    }

    var sourceLabel: String {
        sourceType.label
    }
}

enum CalendarSourceType: String {
    case local
    case exchange
    case calDAV      // Google Calendar, iCloud Calendar
    case subscribed
    case birthdays

    var label: String {
        switch self {
        case .local: "ローカル"
        case .exchange: "Exchange"
        case .calDAV: "CalDAV (Google/iCloud)"
        case .subscribed: "購読"
        case .birthdays: "誕生日"
        }
    }

    var icon: String {
        switch self {
        case .local: "iphone"
        case .exchange: "building.2.fill"
        case .calDAV: "cloud.fill"
        case .subscribed: "link"
        case .birthdays: "gift.fill"
        }
    }
}

struct ExternalCalendarEvent: Identifiable {
    let id: String
    let title: String
    let startDate: Date
    let endDate: Date
    let isAllDay: Bool
    let location: String?
    let calendarName: String
    let calendarSourceType: CalendarSourceType
    let notes: String?

    var timeRange: String {
        if isAllDay {
            return "終日"
        }
        return "\(startDate.shortTimeString) - \(endDate.shortTimeString)"
    }

    var sourceIcon: String {
        calendarSourceType.icon
    }
}
