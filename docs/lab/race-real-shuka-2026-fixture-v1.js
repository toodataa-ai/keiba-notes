/* LAB EXHIBIT v1 — 2026-10-18 Kyoto G1 秋華賞, real starting runners (17).
 * Source: existing immutable pre-start keiba-notes report:
 * docs/reports/2026-10-18-shuka-sho-v3.15-run39078900569-attempt1-v315.html
 * Official JRA entry/form verified before race:
 * https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202604071120261018%2F30
 * The published 9-axis factors are a PRE-RACE MODEL ASSESSMENT, not proven
 * abilities. Styles are PROXIES classified only from FIRST corner rank in
 * the preceding race; not the actual Oct 18 corner outcome. No finishing
 * order, final race time, payoff, popularity or race-result fit is input.
 * No change to JRA predictions, official PDFs, race-engine or bet artifacts.
 */
(function(global){'use strict';
const source=Object.freeze({
 race_id:'2026-10-18-shuka-sho',date:'2026-10-18',
 snapshot:'docs/reports/2026-10-18-shuka-sho-v3.15-run39078900569-attempt1-v315.html',
 prestart:true,horse_count:17,prestart_going:'良',
 source_type:'PRE_RACE_SIGNED_RECORD',postrace_reference_separate:true,
 style_rule:'first_previous_race_corner_fraction<=.13 escape; <=.36 front; <=.70 mid; else rear',
 limit:'Previous race is not necessarily the true preferred running style; grades are uncalibrated model estimates.'
});
const DATA=Object.freeze([
  {
    "number": 1,
    "name": "ギャラボーグ",
    "mark": "△",
    "grade": "B+",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B-",
      "B",
      "B",
      "B-",
      "B",
      "B+"
    ],
    "style": "senko",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 18,
      "first": 5,
      "last": 4,
      "cornerHistory": [
        5,
        4
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "阪神",
        "distance_m": 1600,
        "finish": 2
      }
    ]
  },
  {
    "number": 2,
    "name": "テイエムアイラン",
    "mark": "△",
    "grade": "B",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "B",
      "B",
      "B-",
      "B",
      "B"
    ],
    "style": "nige",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 11,
      "first": 1,
      "last": 1,
      "cornerHistory": [
        1,
        1,
        1
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "中京",
        "distance_m": 1600,
        "finish": 1
      }
    ]
  },
  {
    "number": 3,
    "name": "マスターソアラ",
    "mark": "○",
    "grade": "A",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "A",
      "B",
      "B-",
      "B",
      "A"
    ],
    "style": "oikomi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 11,
      "first": 8,
      "last": 5,
      "cornerHistory": [
        8,
        8,
        6,
        5
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "中山",
        "distance_m": 2000,
        "finish": 1
      }
    ]
  },
  {
    "number": 4,
    "name": "エンネ",
    "mark": "△",
    "grade": "B+",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "A",
      "B",
      "B-",
      "B",
      "B+"
    ],
    "style": "senko",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 12,
      "first": 4,
      "last": 4,
      "cornerHistory": [
        4,
        4
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "阪神",
        "distance_m": 1800,
        "finish": 2
      }
    ]
  },
  {
    "number": 5,
    "name": "タイセイボーグ",
    "mark": "△",
    "grade": "B",
    "pace_grade": "B",
    "factorGrades": [
      "B+",
      "B",
      "A",
      "B+",
      "B",
      "B",
      "B-",
      "B",
      "B"
    ],
    "style": "senko",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 12,
      "first": 4,
      "last": 4,
      "cornerHistory": [
        4,
        4
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "阪神",
        "distance_m": 1800,
        "finish": 12
      }
    ]
  },
  {
    "number": 6,
    "name": "ラベルセーヌ",
    "mark": "△",
    "grade": "B",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "B",
      "B",
      "B-",
      "B",
      "B"
    ],
    "style": "sashi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 10,
      "first": 5,
      "last": 4,
      "cornerHistory": [
        5,
        4
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "新潟",
        "distance_m": 1800,
        "finish": 1
      }
    ]
  },
  {
    "number": 7,
    "name": "バースデイフライト",
    "mark": "×",
    "grade": "C",
    "pace_grade": "B",
    "factorGrades": [
      "B+",
      "B",
      "A",
      "B+",
      "B",
      "B",
      "B-",
      "B",
      "C"
    ],
    "style": "sashi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 12,
      "first": 6,
      "last": 6,
      "cornerHistory": [
        6,
        6
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "阪神",
        "distance_m": 1800,
        "finish": 4
      }
    ]
  },
  {
    "number": 8,
    "name": "モンローウォーク",
    "mark": "▲",
    "grade": "A+",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "B",
      "B",
      "B-",
      "B",
      "A+"
    ],
    "style": "senko",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 12,
      "first": 2,
      "last": 2,
      "cornerHistory": [
        2,
        2
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "阪神",
        "distance_m": 1800,
        "finish": 1
      }
    ]
  },
  {
    "number": 9,
    "name": "スウィートハピネス",
    "mark": "△",
    "grade": "B+",
    "pace_grade": "B",
    "factorGrades": [
      "B+",
      "B",
      "A",
      "B+",
      "B",
      "B",
      "B-",
      "B",
      "B+"
    ],
    "style": "sashi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 12,
      "first": 8,
      "last": 7,
      "cornerHistory": [
        8,
        7
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "阪神",
        "distance_m": 1800,
        "finish": 7
      }
    ]
  },
  {
    "number": 10,
    "name": "ナイスプレーアスク",
    "mark": "×",
    "grade": "C",
    "pace_grade": "B",
    "factorGrades": [
      "B+",
      "B",
      "A",
      "B+",
      "B",
      "B",
      "B-",
      "B",
      "C"
    ],
    "style": "nige",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 11,
      "first": 1,
      "last": 1,
      "cornerHistory": [
        1,
        1,
        1,
        1
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "中山",
        "distance_m": 2000,
        "finish": 6
      }
    ]
  },
  {
    "number": 11,
    "name": "ガーネットフレア",
    "mark": "△",
    "grade": "B",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "A",
      "B",
      "B-",
      "B",
      "B"
    ],
    "style": "senko",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 10,
      "first": 2,
      "last": 2,
      "cornerHistory": [
        2,
        2,
        2,
        2
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "阪神",
        "distance_m": 2000,
        "finish": 1
      }
    ]
  },
  {
    "number": 12,
    "name": "カナルサンマルタン",
    "mark": "△",
    "grade": "B+",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B-",
      "B",
      "B",
      "B-",
      "B",
      "B+"
    ],
    "style": "sashi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 11,
      "first": 5,
      "last": 3,
      "cornerHistory": [
        5,
        3,
        3
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "東京",
        "distance_m": 1800,
        "finish": 1
      }
    ]
  },
  {
    "number": 13,
    "name": "ドリームコア",
    "mark": "◎",
    "grade": "A+",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "A",
      "B",
      "B-",
      "B",
      "A+"
    ],
    "style": "sashi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 11,
      "first": 4,
      "last": 3,
      "cornerHistory": [
        4,
        4,
        5,
        3
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "中山",
        "distance_m": 2000,
        "finish": 3
      }
    ]
  },
  {
    "number": 14,
    "name": "サムシングスイート",
    "mark": "△",
    "grade": "B+",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "A",
      "B",
      "B-",
      "B",
      "B+"
    ],
    "style": "oikomi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 11,
      "first": 9,
      "last": 7,
      "cornerHistory": [
        9,
        8,
        9,
        7
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "中山",
        "distance_m": 2000,
        "finish": 2
      }
    ]
  },
  {
    "number": 15,
    "name": "フェスティバルヒル",
    "mark": "△",
    "grade": "B-",
    "pace_grade": "B",
    "factorGrades": [
      "B+",
      "B",
      "A",
      "B",
      "B",
      "B",
      "B-",
      "B",
      "B-"
    ],
    "style": "sashi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 14,
      "first": 6,
      "last": 7,
      "cornerHistory": [
        6,
        5,
        5,
        7
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "札幌",
        "distance_m": 1800,
        "finish": 14
      }
    ]
  },
  {
    "number": 16,
    "name": "ハヤブササキチャン",
    "mark": "△",
    "grade": "B",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "B",
      "B",
      "B-",
      "B",
      "B"
    ],
    "style": "senko",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 14,
      "first": 4,
      "last": 3,
      "cornerHistory": [
        4,
        4,
        3,
        3
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "札幌",
        "distance_m": 1800,
        "finish": 1
      }
    ]
  },
  {
    "number": 17,
    "name": "ロザーンジュ",
    "mark": "△",
    "grade": "B-",
    "pace_grade": "B+",
    "factorGrades": [
      "B+",
      "B+",
      "A",
      "B+",
      "A",
      "B",
      "B-",
      "B",
      "B-"
    ],
    "style": "sashi",
    "styleMeta": {
      "source": "pre_race_report_last_run",
      "field": 8,
      "first": 3,
      "last": 4,
      "cornerHistory": [
        3,
        3,
        3,
        4
      ],
      "evidence": "2026-10-18発走前固定予想書の前走記録"
    },
    "recentRuns": [
      {
        "venue": "中京",
        "distance_m": 2200,
        "finish": 2
      }
    ]
  }
]);
const id='lab-real-prestart-shuka-2026-17-v1';
function entry(){return {id,demo_mode:'lab_real_prestart_hypothetical',
 date:'2026-10-18',venue:'京都',number:11,race:'第31回秋華賞・実出走馬17頭による仮想展開',
 surface:'芝',turn:'右',distance_m:2000,
 course_id:'kyoto_turf_inner_2000',field_size:17,
 age_restriction_years:3,sex_restriction:'牝',grade_level:'G1',
 scope:'LAB_REAL_PRESTART_INPUT_NOT_ACTUAL_RACE_REPLAY',
 going:'良',going_observed_at:'2026-10-18T08:19:21.108+09:00',
 source_report:source.snapshot};
}
function horses(){return DATA.map(h=>({...h,
 factorGrades:h.factorGrades.slice(),
 styleMeta:{...h.styleMeta},
 recentRuns:h.recentRuns.map(x=>({...x})),
 win_pct:NaN}));}
global.RaceRealShuka2026Fixture=Object.freeze({id,source,entry,horses});
})(typeof window!=='undefined'?window:globalThis);
