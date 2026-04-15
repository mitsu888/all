import SwiftUI
import SwiftData

/// 1日の振り返り・感動メモ画面
/// 音声やテキストで感動・学び・感謝を記録
struct DailyReflectionView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \DailyReflection.createdAt, order: .reverse) private var reflections: [DailyReflection]
    @Query(sort: \ScheduleItem.startDate) private var schedules: [ScheduleItem]
    @Query(sort: \TaskItem.createdAt) private var tasks: [TaskItem]
    @Query(sort: \HabitLog.date, order: .reverse) private var habitLogs: [HabitLog]

    @State private var showAddSheet = false

    private var todayReflection: DailyReflection? {
        reflections.first { Calendar.current.isDateInToday($0.createdAt) }
    }

    var body: some View {
        NavigationStack {
            List {
                // 今日の振り返り
                Section {
                    if let reflection = todayReflection {
                        TodayReflectionCard(reflection: reflection)
                    } else {
                        Button {
                            showAddSheet = true
                        } label: {
                            VStack(spacing: 12) {
                                Image(systemName: "moon.stars.fill")
                                    .font(.system(size: 36))
                                    .foregroundStyle(.indigo)
                                Text("今日の振り返りを記録しましょう")
                                    .font(.headline)
                                Text("感動、学び、感謝を声やテキストで残せます")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 20)
                        }
                        .buttonStyle(.plain)
                    }
                }

                // 過去の振り返り
                if !reflections.isEmpty {
                    Section("過去の振り返り") {
                        ForEach(reflections) { reflection in
                            NavigationLink {
                                ReflectionDetailView(reflection: reflection)
                            } label: {
                                ReflectionRow(reflection: reflection)
                            }
                        }
                        .onDelete(perform: deleteReflections)
                    }
                }

                // 感情の推移（直近7件）
                let recentReflections = Array(reflections.prefix(7)).reversed()
                if recentReflections.count >= 3 {
                    Section("感情の推移") {
                        HStack(spacing: 8) {
                            ForEach(Array(recentReflections), id: \.id) { reflection in
                                VStack(spacing: 4) {
                                    Text(reflection.emotion.emoji)
                                        .font(.title3)
                                    Text(reflection.createdAt.shortWeekday)
                                        .font(.caption2)
                                        .foregroundStyle(.secondary)
                                }
                                .frame(maxWidth: .infinity)
                            }
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
            .navigationTitle("振り返りメモ")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showAddSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showAddSheet) {
                AddReflectionView()
            }
        }
    }

    private func deleteReflections(at offsets: IndexSet) {
        for index in offsets {
            modelContext.delete(reflections[index])
        }
    }
}

struct TodayReflectionCard: View {
    let reflection: DailyReflection

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(reflection.emotion.emoji)
                    .font(.title)
                Text("今日の振り返り")
                    .font(.headline)
                Spacer()
                Text(reflection.createdAt.shortTimeString)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(reflection.content)
                .font(.subheadline)
                .lineLimit(3)

            if !reflection.aiSummary.isEmpty {
                Divider()
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "sparkles")
                        .foregroundStyle(.indigo)
                    Text(reflection.aiSummary)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            // 感動度
            HStack {
                Text("感動度")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                ForEach(1...5, id: \.self) { level in
                    Image(systemName: level <= reflection.impressionLevel ? "star.fill" : "star")
                        .font(.caption)
                        .foregroundStyle(level <= reflection.impressionLevel ? .yellow : .gray)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

struct ReflectionRow: View {
    let reflection: DailyReflection

    var body: some View {
        HStack(spacing: 12) {
            Text(reflection.emotion.emoji)
                .font(.title3)

            VStack(alignment: .leading, spacing: 2) {
                Text(reflection.createdAt.shortDateString)
                    .font(.subheadline)
                    .fontWeight(.medium)
                Text(reflection.content)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer()

            if reflection.isVoiceMemo {
                Image(systemName: "mic.fill")
                    .font(.caption)
                    .foregroundStyle(.indigo)
            }
        }
    }
}

struct ReflectionDetailView: View {
    let reflection: DailyReflection

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                // ヘッダー
                HStack {
                    Text(reflection.emotion.emoji)
                        .font(.largeTitle)
                    VStack(alignment: .leading) {
                        Text(reflection.createdAt.shortDateString)
                            .font(.title3)
                            .fontWeight(.bold)
                        Text(reflection.emotion.label)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    // 感動度
                    HStack(spacing: 2) {
                        ForEach(1...5, id: \.self) { level in
                            Image(systemName: level <= reflection.impressionLevel ? "star.fill" : "star")
                                .foregroundStyle(level <= reflection.impressionLevel ? .yellow : .gray)
                        }
                    }
                }
                .padding()
                .background(Color(.systemGray6))
                .clipShape(RoundedRectangle(cornerRadius: 12))

                // 内容
                Text(reflection.content)
                    .font(.body)

                // AI要約
                if !reflection.aiSummary.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("AIの要約", systemImage: "sparkles")
                            .font(.headline)
                            .foregroundStyle(.indigo)
                        Text(reflection.aiSummary)
                            .font(.subheadline)
                    }
                    .padding()
                    .background(Color.indigo.opacity(0.05))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                // 学んだこと
                if !reflection.learnings.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("学んだこと", systemImage: "lightbulb.fill")
                            .font(.headline)
                            .foregroundStyle(.orange)
                        ForEach(reflection.learnings, id: \.self) { learning in
                            HStack(alignment: .top) {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundStyle(.orange)
                                    .font(.caption)
                                    .padding(.top, 2)
                                Text(learning)
                                    .font(.subheadline)
                            }
                        }
                    }
                    .padding()
                    .background(Color.orange.opacity(0.05))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                // 感謝
                if !reflection.gratitudes.isEmpty {
                    VStack(alignment: .leading, spacing: 8) {
                        Label("感謝すること", systemImage: "heart.fill")
                            .font(.headline)
                            .foregroundStyle(.pink)
                        ForEach(reflection.gratitudes, id: \.self) { gratitude in
                            HStack(alignment: .top) {
                                Image(systemName: "heart.fill")
                                    .foregroundStyle(.pink)
                                    .font(.caption)
                                    .padding(.top, 2)
                                Text(gratitude)
                                    .font(.subheadline)
                            }
                        }
                    }
                    .padding()
                    .background(Color.pink.opacity(0.05))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                // タグ
                if !reflection.tags.isEmpty {
                    FlowLayout(spacing: 8) {
                        ForEach(reflection.tags, id: \.self) { tag in
                            Text("#\(tag)")
                                .font(.caption)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 4)
                                .background(Color.indigo.opacity(0.1))
                                .foregroundStyle(.indigo)
                                .clipShape(Capsule())
                        }
                    }
                }
            }
            .padding()
        }
        .navigationTitle("振り返り詳細")
        #if os(iOS)
        .navigationBarTitleDisplayMode(.inline)
        #endif
    }
}

/// シンプルなFlowLayout
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = layout(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = layout(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y), proposal: .unspecified)
        }
    }

    private func layout(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, positions: [CGPoint]) {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var maxHeight: CGFloat = 0
        var rowMaxHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth && x > 0 {
                x = 0
                y += rowMaxHeight + spacing
                rowMaxHeight = 0
            }
            positions.append(CGPoint(x: x, y: y))
            rowMaxHeight = max(rowMaxHeight, size.height)
            x += size.width + spacing
            maxHeight = max(maxHeight, y + rowMaxHeight)
        }

        return (CGSize(width: maxWidth, height: maxHeight), positions)
    }
}

struct AddReflectionView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    @Query(sort: \ScheduleItem.startDate) private var schedules: [ScheduleItem]
    @Query(sort: \TaskItem.createdAt) private var tasks: [TaskItem]
    @Query(sort: \HabitLog.date, order: .reverse) private var habitLogs: [HabitLog]

    @StateObject private var reflectionService = ReflectionService()
    @StateObject private var speechService = SpeechService()

    @State private var content = ""
    @State private var emotion: Emotion = .neutral
    @State private var impressionLevel = 3
    @State private var isAnalyzing = false

    var body: some View {
        NavigationStack {
            Form {
                Section("今日の気持ち") {
                    HStack(spacing: 16) {
                        ForEach(Emotion.allCases, id: \.self) { e in
                            Button {
                                emotion = e
                            } label: {
                                VStack(spacing: 4) {
                                    Text(e.emoji)
                                        .font(.title)
                                        .scaleEffect(emotion == e ? 1.3 : 1.0)
                                    Text(e.label)
                                        .font(.caption2)
                                        .foregroundStyle(emotion == e ? .primary : .secondary)
                                }
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                }

                Section("感動度") {
                    HStack {
                        ForEach(1...5, id: \.self) { level in
                            Button {
                                impressionLevel = level
                            } label: {
                                Image(systemName: level <= impressionLevel ? "star.fill" : "star")
                                    .font(.title2)
                                    .foregroundStyle(level <= impressionLevel ? .yellow : .gray)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 4)
                }

                Section("振り返り内容") {
                    TextEditor(text: $content)
                        .frame(minHeight: 120)

                    // 音声入力ボタン
                    HStack {
                        Spacer()
                        Button {
                            if speechService.isRecording {
                                speechService.stopRecording()
                                if !speechService.transcribedText.isEmpty {
                                    if !content.isEmpty { content += "\n" }
                                    content += speechService.transcribedText
                                }
                            } else {
                                Task { await speechService.startRecording() }
                            }
                        } label: {
                            Label(
                                speechService.isRecording ? "録音停止" : "音声で入力",
                                systemImage: speechService.isRecording ? "stop.circle.fill" : "mic.circle.fill"
                            )
                            .foregroundStyle(speechService.isRecording ? .red : .indigo)
                        }
                        Spacer()
                    }

                    if speechService.isRecording {
                        HStack {
                            ProgressView()
                            Text("聴いています...")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                if isAnalyzing {
                    Section {
                        HStack {
                            ProgressView()
                            Text("AIが分析しています...")
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .navigationTitle("今日の振り返り")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("キャンセル") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        Task { await saveReflection() }
                    }
                    .disabled(content.isEmpty || isAnalyzing)
                }
            }
        }
    }

    private func saveReflection() async {
        isAnalyzing = true
        defer { isAnalyzing = false }

        let reflection = DailyReflection(
            content: content,
            emotion: emotion,
            impressionLevel: impressionLevel,
            isVoiceMemo: speechService.transcribedText.isEmpty == false
        )

        // AI分析
        if appState.isAPIKeySet {
            reflectionService.setup(apiKey: appState.apiKey)

            let todaySchedules = schedules.filter { $0.startDate.isToday }
            let completedTasks = tasks.filter { $0.isCompleted && $0.completedAt?.isToday == true }
            let todayHabitLogs = habitLogs.filter { Calendar.current.isDateInToday($0.date) }

            if let analysis = try? await reflectionService.analyzeReflection(
                content: content,
                todaySchedules: todaySchedules,
                completedTasks: completedTasks,
                habitLogs: todayHabitLogs
            ) {
                reflection.aiSummary = analysis.summary
                reflection.emotion = analysis.detectedEmotion
                reflection.impressionLevel = analysis.impressionLevel
                reflection.learnings = analysis.learnings
                reflection.gratitudes = analysis.gratitudes
                reflection.tags = analysis.tags
            }
        }

        modelContext.insert(reflection)
        try? modelContext.save()
        dismiss()
    }
}
