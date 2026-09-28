/*
========================================================
BUSIDOL WIKI - COMPLETE CHARACTER DATABASE
========================================================

Phạm vi:
- Đầy đủ ID 1 -> 114.
- Nhân vật thường 1★ -> 8★.
- Các nhân vật đặc biệt / anh hùng 8★.
- Đầy đủ nhân vật 9★ hiện có trong source.

Nguồn:
- CHAR_OUR_TEAM trong bundle game.
- Database 1★–8★ đã dựng trước đó.

Quy ước:
- ID là khóa chính duy nhất.
- Không tự sửa stat của game.
- AP/HP dưới đây là BASE stat.
- Portrait:
  ../ELDORADO_WEB/source_20240722/image/ui/4_game/char/
  ga_ally_{ID}.jpg

Công thức stat theo level:
Math.round(
    start
    + (end - start)
    * (level - 1)
    / (maxLevel - 1)
)
========================================================
*/


/*
========================================================
ASSET PATHS
========================================================
*/

const CHARACTER_PORTRAIT_BASE =
    "../ELDORADO_WEB/source_20240722/image/ui/4_game/char/";

const CHARACTER_BATTLE_BASE =
    "../ELDORADO_WEB/source_20240722/image/char/";


/*
========================================================
PORTRAIT
========================================================
*/

function getCharacterPortrait(character) {
    const id =
        Number(character.id);

    return (
        CHARACTER_PORTRAIT_BASE
        +
        "ga_ally_"
        +
        id
        +
        ".jpg"
    );
}


/*
========================================================
BATTLE FOLDER
========================================================
*/

function getCharacterBattleFolder(character) {
    const id =
        Number(character.id);

    return (
        CHARACTER_BATTLE_BASE
        +
        "ally_"
        +
        id
        +
        "/"
    );
}


/*
========================================================
CHARACTER DATA
ID 1 -> 114
========================================================
*/

const CHARACTERS = [

    {
        id: 1,
        name: "ACE",
        sourceAsset: "ally_01",
        star: 1,
        maxLevel: 20,
        apStart: 2,
        apEnd: 35,
        hpStart: 10,
        hpEnd: 200
    },

    {
        id: 2,
        name: "ECHO",
        sourceAsset: "ally_02",
        star: 1,
        maxLevel: 20,
        apStart: 1,
        apEnd: 20,
        hpStart: 10,
        hpEnd: 180
    },

    {
        id: 3,
        name: "SMARTY",
        sourceAsset: "ally_03",
        star: 1,
        maxLevel: 20,
        apStart: 3,
        apEnd: 30,
        hpStart: 13,
        hpEnd: 260
    },

    {
        id: 4,
        name: "KHAN",
        sourceAsset: "ally_04",
        star: 1,
        maxLevel: 20,
        apStart: 2,
        apEnd: 25,
        hpStart: 30,
        hpEnd: 600
    },

    {
        id: 5,
        name: "ACE II",
        sourceAsset: "ally_05",
        star: 2,
        maxLevel: 30,
        apStart: 3,
        apEnd: 53,
        hpStart: 15,
        hpEnd: 300
    },

    {
        id: 6,
        name: "ACE III",
        sourceAsset: "ally_06",
        star: 3,
        maxLevel: 40,
        apStart: 6,
        apEnd: 105,
        hpStart: 30,
        hpEnd: 600
    },

    {
        id: 7,
        name: "ACE IV",
        sourceAsset: "ally_07",
        star: 4,
        maxLevel: 50,
        apStart: 15,
        apEnd: 263,
        hpStart: 75,
        hpEnd: 1500
    },

    {
        id: 8,
        name: "ACE V",
        sourceAsset: "ally_08",
        star: 5,
        maxLevel: 60,
        apStart: 45,
        apEnd: 788,
        hpStart: 225,
        hpEnd: 4500
    },

    {
        id: 9,
        name: "ACE VI",
        sourceAsset: "ally_09",
        star: 6,
        maxLevel: 70,
        apStart: 158,
        apEnd: 2757,
        hpStart: 788,
        hpEnd: 15750
    },

    {
        id: 10,
        name: "ECHO II",
        sourceAsset: "ally_10",
        star: 2,
        maxLevel: 30,
        apStart: 2,
        apEnd: 30,
        hpStart: 12,
        hpEnd: 360
    },

    {
        id: 11,
        name: "ECHO III",
        sourceAsset: "ally_11",
        star: 3,
        maxLevel: 40,
        apStart: 3,
        apEnd: 60,
        hpStart: 30,
        hpEnd: 540
    },

    {
        id: 12,
        name: "ECHO IV",
        sourceAsset: "ally_12",
        star: 4,
        maxLevel: 50,
        apStart: 8,
        apEnd: 150,
        hpStart: 75,
        hpEnd: 1350
    },

    {
        id: 13,
        name: "ECHO V",
        sourceAsset: "ally_13",
        star: 5,
        maxLevel: 60,
        apStart: 23,
        apEnd: 450,
        hpStart: 225,
        hpEnd: 4050
    },

    {
        id: 14,
        name: "ECHO VI",
        sourceAsset: "ally_14",
        star: 6,
        maxLevel: 70,
        apStart: 79,
        apEnd: 1575,
        hpStart: 788,
        hpEnd: 14175
    },

    {
        id: 15,
        name: "SMARTY II",
        sourceAsset: "ally_15",
        star: 2,
        maxLevel: 30,
        apStart: 5,
        apEnd: 45,
        hpStart: 20,
        hpEnd: 390
    },

    {
        id: 16,
        name: "SMARTY III",
        sourceAsset: "ally_16",
        star: 3,
        maxLevel: 40,
        apStart: 9,
        apEnd: 90,
        hpStart: 39,
        hpEnd: 780
    },

    {
        id: 17,
        name: "SMARTY IV",
        sourceAsset: "ally_17",
        star: 4,
        maxLevel: 50,
        apStart: 23,
        apEnd: 225,
        hpStart: 98,
        hpEnd: 1950
    },

    {
        id: 18,
        name: "SMARTY V",
        sourceAsset: "ally_18",
        star: 5,
        maxLevel: 60,
        apStart: 68,
        apEnd: 675,
        hpStart: 293,
        hpEnd: 5850
    },

    {
        id: 19,
        name: "SMARTY VI",
        sourceAsset: "ally_19",
        star: 6,
        maxLevel: 70,
        apStart: 237,
        apEnd: 2363,
        hpStart: 1024,
        hpEnd: 20475
    },

    {
        id: 20,
        name: "KHAN II",
        sourceAsset: "ally_20",
        star: 2,
        maxLevel: 30,
        apStart: 3,
        apEnd: 38,
        hpStart: 45,
        hpEnd: 900
    },

    {
        id: 21,
        name: "KHAN III",
        sourceAsset: "ally_21",
        star: 3,
        maxLevel: 40,
        apStart: 6,
        apEnd: 75,
        hpStart: 90,
        hpEnd: 1800
    },

    {
        id: 22,
        name: "KHAN IV",
        sourceAsset: "ally_22",
        star: 4,
        maxLevel: 50,
        apStart: 15,
        apEnd: 188,
        hpStart: 225,
        hpEnd: 4500
    },

    {
        id: 23,
        name: "KHAN V",
        sourceAsset: "ally_23",
        star: 5,
        maxLevel: 60,
        apStart: 45,
        apEnd: 563,
        hpStart: 675,
        hpEnd: 13500
    },

    {
        id: 24,
        name: "KHAN VI",
        sourceAsset: "ally_24",
        star: 6,
        maxLevel: 70,
        apStart: 158,
        apEnd: 1969,
        hpStart: 2363,
        hpEnd: 47250
    },

    {
        id: 25,
        name: "LODY I",
        sourceAsset: "ally_25",
        star: 1,
        maxLevel: 20,
        apStart: 3,
        apEnd: 40,
        hpStart: 12,
        hpEnd: 240
    },

    {
        id: 26,
        name: "LODY II",
        sourceAsset: "ally_26",
        star: 2,
        maxLevel: 30,
        apStart: 5,
        apEnd: 60,
        hpStart: 18,
        hpEnd: 360
    },

    {
        id: 27,
        name: "LODY III",
        sourceAsset: "ally_27",
        star: 3,
        maxLevel: 40,
        apStart: 9,
        apEnd: 120,
        hpStart: 36,
        hpEnd: 720
    },

    {
        id: 28,
        name: "LODY IV",
        sourceAsset: "ally_28",
        star: 4,
        maxLevel: 50,
        apStart: 23,
        apEnd: 300,
        hpStart: 90,
        hpEnd: 1800
    },

    {
        id: 29,
        name: "LODY V",
        sourceAsset: "ally_29",
        star: 5,
        maxLevel: 60,
        apStart: 68,
        apEnd: 900,
        hpStart: 270,
        hpEnd: 5400
    },

    {
        id: 30,
        name: "LODY VI",
        sourceAsset: "ally_30",
        star: 6,
        maxLevel: 70,
        apStart: 237,
        apEnd: 3150,
        hpStart: 945,
        hpEnd: 18900
    },

    {
        id: 31,
        name: "BEBEE I",
        sourceAsset: "ally_31",
        star: 1,
        maxLevel: 20,
        apStart: 2,
        apEnd: 35,
        hpStart: 10,
        hpEnd: 200
    },

    {
        id: 32,
        name: "BEBEE II",
        sourceAsset: "ally_32",
        star: 2,
        maxLevel: 30,
        apStart: 3,
        apEnd: 53,
        hpStart: 15,
        hpEnd: 300
    },

    {
        id: 33,
        name: "BEBEE III",
        sourceAsset: "ally_33",
        star: 3,
        maxLevel: 40,
        apStart: 6,
        apEnd: 105,
        hpStart: 30,
        hpEnd: 600
    },

    {
        id: 34,
        name: "BEBEE IV",
        sourceAsset: "ally_34",
        star: 4,
        maxLevel: 50,
        apStart: 15,
        apEnd: 263,
        hpStart: 75,
        hpEnd: 1500
    },

    {
        id: 35,
        name: "BEBEE V",
        sourceAsset: "ally_35",
        star: 5,
        maxLevel: 60,
        apStart: 45,
        apEnd: 788,
        hpStart: 225,
        hpEnd: 4500
    },

    {
        id: 36,
        name: "BEBEE VI",
        sourceAsset: "ally_36",
        star: 6,
        maxLevel: 70,
        apStart: 158,
        apEnd: 2757,
        hpStart: 1463,
        hpEnd: 29250
    },

    {
        id: 37,
        name: "RUBY I",
        sourceAsset: "ally_37",
        star: 1,
        maxLevel: 20,
        apStart: 3,
        apEnd: 30,
        hpStart: 13,
        hpEnd: 260
    },

    {
        id: 38,
        name: "RUBY II",
        sourceAsset: "ally_38",
        star: 2,
        maxLevel: 30,
        apStart: 5,
        apEnd: 45,
        hpStart: 20,
        hpEnd: 390
    },

    {
        id: 39,
        name: "RUBY III",
        sourceAsset: "ally_39",
        star: 3,
        maxLevel: 40,
        apStart: 9,
        apEnd: 90,
        hpStart: 39,
        hpEnd: 780
    },

    {
        id: 40,
        name: "RUBY IV",
        sourceAsset: "ally_40",
        star: 4,
        maxLevel: 50,
        apStart: 23,
        apEnd: 225,
        hpStart: 98,
        hpEnd: 1950
    },

    {
        id: 41,
        name: "RUBY V",
        sourceAsset: "ally_41",
        star: 5,
        maxLevel: 60,
        apStart: 68,
        apEnd: 675,
        hpStart: 293,
        hpEnd: 5850
    },

    {
        id: 42,
        name: "RUBY VI",
        sourceAsset: "ally_42",
        star: 6,
        maxLevel: 70,
        apStart: 237,
        apEnd: 2363,
        hpStart: 1024,
        hpEnd: 20475
    },

    {
        id: 43,
        name: "GOLDMAN II",
        sourceAsset: "ally_43",
        star: 2,
        maxLevel: 30,
        apStart: 3,
        apEnd: 53,
        hpStart: 20,
        hpEnd: 390
    },

    {
        id: 44,
        name: "GOLDMAN III",
        sourceAsset: "ally_44",
        star: 3,
        maxLevel: 40,
        apStart: 6,
        apEnd: 105,
        hpStart: 39,
        hpEnd: 780
    },

    {
        id: 45,
        name: "GOLDMAN IV",
        sourceAsset: "ally_45",
        star: 4,
        maxLevel: 50,
        apStart: 15,
        apEnd: 263,
        hpStart: 98,
        hpEnd: 1950
    },

    {
        id: 46,
        name: "GOLDMAN V",
        sourceAsset: "ally_46",
        star: 5,
        maxLevel: 60,
        apStart: 47,
        apEnd: 814,
        hpStart: 303,
        hpEnd: 6045
    },

    {
        id: 47,
        name: "GOLDMAN VI",
        sourceAsset: "ally_47",
        star: 6,
        maxLevel: 70,
        apStart: 163,
        apEnd: 2849,
        hpStart: 1058,
        hpEnd: 21158
    },

    {
        id: 48,
        name: "GOLDMAN VII",
        sourceAsset: "ally_48",
        star: 7,
        maxLevel: 80,
        apStart: 651,
        apEnd: 11393,
        hpStart: 4232,
        hpEnd: 84630
    },

    {
        id: 49,
        name: "RUSY VII",
        sourceAsset: "ally_49",
        star: 7,
        maxLevel: 80,
        apStart: 709,
        apEnd: 9450,
        hpStart: 2835,
        hpEnd: 56700
    },

    {
        id: 50,
        name: "RUSY VII",
        sourceAsset: "ally_50",
        star: 7,
        maxLevel: 80,
        apStart: 945,
        apEnd: 12600,
        hpStart: 3780,
        hpEnd: 75600
    },

    {
        id: 51,
        name: "GINGERMAN II",
        sourceAsset: "ally_51",
        star: 2,
        maxLevel: 30,
        apStart: 3,
        apEnd: 53,
        hpStart: 20,
        hpEnd: 390
    },

    {
        id: 52,
        name: "GINGERMAN III",
        sourceAsset: "ally_52",
        star: 3,
        maxLevel: 40,
        apStart: 6,
        apEnd: 105,
        hpStart: 39,
        hpEnd: 780
    },

    {
        id: 53,
        name: "GINGERMAN IV",
        sourceAsset: "ally_53",
        star: 4,
        maxLevel: 50,
        apStart: 15,
        apEnd: 263,
        hpStart: 98,
        hpEnd: 1950
    },

    {
        id: 54,
        name: "GINGERMAN V",
        sourceAsset: "ally_54",
        star: 5,
        maxLevel: 60,
        apStart: 45,
        apEnd: 788,
        hpStart: 293,
        hpEnd: 5850
    },

    {
        id: 55,
        name: "GINGERMAN VI",
        sourceAsset: "ally_55",
        star: 6,
        maxLevel: 70,
        apStart: 158,
        apEnd: 2757,
        hpStart: 1024,
        hpEnd: 20475
    },

    {
        id: 56,
        name: "GINGERMAN VII",
        sourceAsset: "ally_56",
        star: 7,
        maxLevel: 80,
        apStart: 630,
        apEnd: 11025,
        hpStart: 4095,
        hpEnd: 81900
    },

    {
        id: 57,
        name: "BENSI II",
        sourceAsset: "ally_57",
        star: 2,
        maxLevel: 30,
        apStart: 5,
        apEnd: 48,
        hpStart: 21,
        hpEnd: 416
    },

    {
        id: 58,
        name: "BENSI III",
        sourceAsset: "ally_58",
        star: 3,
        maxLevel: 40,
        apStart: 10,
        apEnd: 96,
        hpStart: 42,
        hpEnd: 832
    },

    {
        id: 59,
        name: "BENSI IV",
        sourceAsset: "ally_59",
        star: 4,
        maxLevel: 50,
        apStart: 24,
        apEnd: 240,
        hpStart: 104,
        hpEnd: 2080
    },

    {
        id: 60,
        name: "BENSI V",
        sourceAsset: "ally_60",
        star: 5,
        maxLevel: 60,
        apStart: 72,
        apEnd: 720,
        hpStart: 312,
        hpEnd: 6240
    },

    {
        id: 61,
        name: "BENSI VI",
        sourceAsset: "ally_61",
        star: 6,
        maxLevel: 70,
        apStart: 252,
        apEnd: 2520,
        hpStart: 1092,
        hpEnd: 21840
    },

    {
        id: 62,
        name: "BENSI VII",
        sourceAsset: "ally_62",
        star: 7,
        maxLevel: 80,
        apStart: 1008,
        apEnd: 10080,
        hpStart: 4368,
        hpEnd: 87360
    },

    {
        id: 63,
        name: "ACE VII",
        sourceAsset: "ally_63",
        star: 7,
        maxLevel: 80,
        apStart: 630,
        apEnd: 11025,
        hpStart: 3150,
        hpEnd: 63
    },

    {
        id: 64,
        name: "BEBEE VII",
        sourceAsset: "ally_64",
        star: 7,
        maxLevel: 80,
        apStart: 630,
        apEnd: 11025,
        hpStart: 5850,
        hpEnd: 117
    },

    {
        id: 65,
        name: "RUBY VII",
        sourceAsset: "ally_65",
        star: 7,
        maxLevel: 80,
        apStart: 945,
        apEnd: 9450,
        hpStart: 4095,
        hpEnd: 81900
    },

    {
        id: 66,
        name: "ECHO VII",
        sourceAsset: "ally_66",
        star: 7,
        maxLevel: 80,
        apStart: 315,
        apEnd: 6300,
        hpStart: 3150,
        hpEnd: 56700
    },

    {
        id: 67,
        name: "SMARTY VII",
        sourceAsset: "ally_67",
        star: 7,
        maxLevel: 80,
        apStart: 945,
        apEnd: 9450,
        hpStart: 4095,
        hpEnd: 81900
    },

    {
        id: 68,
        name: "KHAN VII",
        sourceAsset: "ally_68",
        star: 7,
        maxLevel: 80,
        apStart: 1,
        apEnd: 1,
        hpStart: 14175,
        hpEnd: 283500
    },

    {
        id: 69,
        name: "JEY I",
        sourceAsset: "ally_69",
        star: 1,
        maxLevel: 20,
        apStart: 1,
        apEnd: 25,
        hpStart: 10,
        hpEnd: 150
    },

    {
        id: 70,
        name: "JEY II",
        sourceAsset: "ally_70",
        star: 2,
        maxLevel: 30,
        apStart: 2,
        apEnd: 40,
        hpStart: 16,
        hpEnd: 240
    },

    {
        id: 71,
        name: "JEY III",
        sourceAsset: "ally_71",
        star: 3,
        maxLevel: 40,
        apStart: 4,
        apEnd: 80,
        hpStart: 32,
        hpEnd: 480
    },

    {
        id: 72,
        name: "JEY IV",
        sourceAsset: "ally_72",
        star: 4,
        maxLevel: 50,
        apStart: 8,
        apEnd: 200,
        hpStart: 80,
        hpEnd: 1200
    },

    {
        id: 73,
        name: "JEY V",
        sourceAsset: "ally_73",
        star: 5,
        maxLevel: 60,
        apStart: 24,
        apEnd: 600,
        hpStart: 240,
        hpEnd: 3600
    },

    {
        id: 74,
        name: "JEY VI",
        sourceAsset: "ally_74",
        star: 6,
        maxLevel: 70,
        apStart: 84,
        apEnd: 2100,
        hpStart: 840,
        hpEnd: 12600
    },

    {
        id: 75,
        name: "JEY VII",
        sourceAsset: "ally_75",
        star: 7,
        maxLevel: 80,
        apStart: 378,
        apEnd: 9450,
        hpStart: 3780,
        hpEnd: 56700
    },

    {
        id: 76,
        name: "COW II",
        sourceAsset: "ally_76",
        star: 2,
        maxLevel: 30,
        apStart: 4,
        apEnd: 48,
        hpStart: 1,
        hpEnd: 1
    },

    {
        id: 77,
        name: "COW III",
        sourceAsset: "ally_77",
        star: 3,
        maxLevel: 40,
        apStart: 7,
        apEnd: 96,
        hpStart: 1,
        hpEnd: 1
    },

    {
        id: 78,
        name: "COW IV",
        sourceAsset: "ally_78",
        star: 4,
        maxLevel: 50,
        apStart: 16,
        apEnd: 240,
        hpStart: 1,
        hpEnd: 1
    },

    {
        id: 79,
        name: "COW V",
        sourceAsset: "ally_79",
        star: 5,
        maxLevel: 60,
        apStart: 48,
        apEnd: 720,
        hpStart: 1,
        hpEnd: 1
    },

    {
        id: 80,
        name: "COW VI",
        sourceAsset: "ally_80",
        star: 6,
        maxLevel: 70,
        apStart: 168,
        apEnd: 2520,
        hpStart: 1,
        hpEnd: 1
    },

    {
        id: 81,
        name: "COW VII",
        sourceAsset: "ally_81",
        star: 7,
        maxLevel: 80,
        apStart: 672,
        apEnd: 10080,
        hpStart: 1,
        hpEnd: 1
    },

    {
        id: 82,
        name: "ACE VIII",
        sourceAsset: "ally_82",
        star: 8,
        maxLevel: 90,
        apStart: 2835,
        apEnd: 49613,
        hpStart: 14175,
        hpEnd: 283500
    },

    {
        id: 83,
        name: "ECHO VIII",
        sourceAsset: "ally_83",
        star: 8,
        maxLevel: 90,
        apStart: 1418,
        apEnd: 28350,
        hpStart: 14175,
        hpEnd: 255150
    },

    {
        id: 84,
        name: "SMARTY VIII",
        sourceAsset: "ally_84",
        star: 8,
        maxLevel: 90,
        apStart: 4253,
        apEnd: 42525,
        hpStart: 18428,
        hpEnd: 368550
    },

    {
        id: 85,
        name: "KHAN VIII",
        sourceAsset: "ally_85",
        star: 8,
        maxLevel: 90,
        apStart: 300,
        apEnd: 3,
        hpStart: 63788,
        hpEnd: 1275750
    },

    {
        id: 86,
        name: "RUSY VIII",
        sourceAsset: "ally_86",
        star: 8,
        maxLevel: 90,
        apStart: 4253,
        apEnd: 56700,
        hpStart: 17010,
        hpEnd: 340200
    },

    {
        id: 87,
        name: "RUSY VIII",
        sourceAsset: "ally_87",
        star: 8,
        maxLevel: 90,
        apStart: 2835,
        apEnd: 37800,
        hpStart: 11340,
        hpEnd: 226800
    },

    {
        id: 88,
        name: "BEBEE VIII",
        sourceAsset: "ally_88",
        star: 8,
        maxLevel: 90,
        apStart: 2520,
        apEnd: 44100,
        hpStart: 11700,
        hpEnd: 234
    },

    {
        id: 89,
        name: "RUBY VIII",
        sourceAsset: "ally_89",
        star: 8,
        maxLevel: 90,
        apStart: 4253,
        apEnd: 42525,
        hpStart: 18428,
        hpEnd: 368550
    },

    {
        id: 90,
        name: "GOLDMAN VIII",
        sourceAsset: "ally_90",
        star: 8,
        maxLevel: 90,
        apStart: 2930,
        apEnd: 51267,
        hpStart: 19042,
        hpEnd: 380835
    },

    {
        id: 91,
        name: "GINGERMAN VIII",
        sourceAsset: "ally_91",
        star: 8,
        maxLevel: 90,
        apStart: 2835,
        apEnd: 49613,
        hpStart: 18428,
        hpEnd: 368550
    },

    {
        id: 92,
        name: "BENSI VIII",
        sourceAsset: "ally_92",
        star: 8,
        maxLevel: 90,
        apStart: 4536,
        apEnd: 45360,
        hpStart: 19656,
        hpEnd: 393120
    },

    {
        id: 93,
        name: "JEY VIII",
        sourceAsset: "ally_93",
        star: 8,
        maxLevel: 90,
        apStart: 1890,
        apEnd: 47250,
        hpStart: 18900,
        hpEnd: 283500
    },

    {
        id: 94,
        name: "COW VIII",
        sourceAsset: "ally_94",
        star: 8,
        maxLevel: 90,
        apStart: 3024,
        apEnd: 45360,
        hpStart: 1,
        hpEnd: 1
    },

    {
        id: 95,
        name: "Azure Dragon",
        sourceAsset: "ally_95",
        star: 8,
        maxLevel: 90,
        apStart: 15000,
        apEnd: 250000,
        hpStart: 150000,
        hpEnd: 1500000
    },

    {
        id: 96,
        name: "Mercenary Thrue",
        sourceAsset: "ally_96",
        star: 4,
        maxLevel: 50,
        apStart: 18,
        apEnd: 315,
        hpStart: 90,
        hpEnd: 1800
    },

    {
        id: 97,
        name: "Warrior Thrue",
        sourceAsset: "ally_97",
        star: 5,
        maxLevel: 60,
        apStart: 54,
        apEnd: 945,
        hpStart: 270,
        hpEnd: 5400
    },

    {
        id: 98,
        name: "Knight Thrue",
        sourceAsset: "ally_98",
        star: 6,
        maxLevel: 70,
        apStart: 189,
        apEnd: 3308,
        hpStart: 945,
        hpEnd: 18900
    },

    {
        id: 99,
        name: "Valkyrie Thrue",
        sourceAsset: "ally_99",
        star: 7,
        maxLevel: 80,
        apStart: 756,
        apEnd: 13230,
        hpStart: 3780,
        hpEnd: 75600
    },

    {
        id: 100,
        name: "WarGod Thrue",
        sourceAsset: "ally_100",
        star: 8,
        maxLevel: 90,
        apStart: 3402,
        apEnd: 59535,
        hpStart: 17010,
        hpEnd: 340200
    },

    {
        id: 101,
        name: "White Tiger",
        sourceAsset: "ally_101",
        star: 8,
        maxLevel: 90,
        apStart: 20000,
        apEnd: 300000,
        hpStart: 150000,
        hpEnd: 1500000
    },

    {
        id: 102,
        name: "Tortoise Warrior",
        sourceAsset: "ally_102",
        star: 8,
        maxLevel: 90,
        apStart: 1,
        apEnd: 1,
        hpStart: 150000,
        hpEnd: 3000000
    },

    {
        id: 103,
        name: "Vermilion Bird",
        sourceAsset: "ally_103",
        star: 8,
        maxLevel: 90,
        apStart: 11250,
        apEnd: 187500,
        hpStart: 112500,
        hpEnd: 1875000
    },

    {
        id: 104,
        name: "Ogong",
        sourceAsset: "ally_104",
        star: 8,
        maxLevel: 90,
        apStart: 20000,
        apEnd: 300000,
        hpStart: 150000,
        hpEnd: 3000000
    },

    {
        id: 105,
        name: "Mukhyang",
        sourceAsset: "ally_105",
        star: 8,
        maxLevel: 90,
        apStart: 20000,
        apEnd: 300000,
        hpStart: 1,
        hpEnd: 46
    },

    {
        id: 106,
        name: "Spirit Serpent",
        sourceAsset: "ally_106",
        star: 8,
        maxLevel: 90,
        apStart: 15000,
        apEnd: 200000,
        hpStart: 100000,
        hpEnd: 2000000
    },

    {
        id: 107,
        name: "Flame Cavalier",
        sourceAsset: "ally_107",
        star: 8,
        maxLevel: 90,
        apStart: 2500,
        apEnd: 40000,
        hpStart: 1,
        hpEnd: 46
    },

    {
        id: 108,
        name: "Mermaid Lucy",
        sourceAsset: "ally_108",
        star: 9,
        maxLevel: 100,
        apStart: 21000,
        apEnd: 280000,
        hpStart: 85000,
        hpEnd: 1700000
    },

    {
        id: 109,
        name: "Influencer Lucy",
        sourceAsset: "ally_109",
        star: 9,
        maxLevel: 100,
        apStart: 14000,
        apEnd: 190000,
        hpStart: 56000,
        hpEnd: 1200000
    },

    {
        id: 110,
        name: "Orchestra Koo",
        sourceAsset: "ally_110",
        star: 9,
        maxLevel: 100,
        apStart: 16000,
        apEnd: 230000,
        hpStart: 1,
        hpEnd: 1
    },

    {
        id: 111,
        name: "Party Animal Thrue",
        sourceAsset: "ally_111",
        star: 9,
        maxLevel: 100,
        apStart: 18000,
        apEnd: 300000,
        hpStart: 85000,
        hpEnd: 1700000
    },

    {
        id: 112,
        name: "Black Raven",
        sourceAsset: "ally_112",
        star: 8,
        maxLevel: 90,
        apStart: 10000,
        apEnd: 150000,
        hpStart: 100000,
        hpEnd: 2000000
    },

    {
        id: 113,
        name: "Fallen Angel Gingerman",
        sourceAsset: "ally_113",
        star: 9,
        maxLevel: 100,
        apStart: 14000,
        apEnd: 240000,
        hpStart: 90000,
        hpEnd: 1800000
    },

    {
        id: 114,
        name: "Hades Bebee",
        sourceAsset: "ally_114",
        star: 9,
        maxLevel: 100,
        apStart: 10000,
        apEnd: 150000,
        hpStart: 70000,
        hpEnd: 1400000
    }

];


/*
========================================================
STAT CALCULATION
========================================================
*/

function calculateCharacterStat(
    start,
    end,
    maxLevel,
    level
) {
    const safeStart =
        Number(start);

    const safeEnd =
        Number(end);

    const safeMaxLevel =
        Number(maxLevel);

    const safeLevel =
        Number(level);

    if (safeLevel <= 1) {
        return safeStart;
    }

    if (safeLevel >= safeMaxLevel) {
        return safeEnd;
    }

    return Math.round(
        safeStart
        +
        (
            safeEnd
            -
            safeStart
        )
        *
        (
            safeLevel
            -
            1
        )
        /
        (
            safeMaxLevel
            -
            1
        )
    );
}


/*
========================================================
GET CHARACTER BY ID
========================================================
*/

function getCharacterById(id) {
    const targetId =
        Number(id);

    return (
        CHARACTERS.find(
            character =>
                character.id === targetId
        )
        ||
        null
    );
}


/*
========================================================
GET CHARACTERS BY STAR
========================================================
*/

function getCharactersByStar(star) {
    const targetStar =
        Number(star);

    return CHARACTERS.filter(
        character =>
            character.star === targetStar
    );
}


/*
========================================================
GET FULL LEVEL TABLE
========================================================
*/

function getCharacterLevelStats(character) {
    const result = [];

    for (
        let level = 1;
        level <= character.maxLevel;
        level++
    ) {
        result.push({
            level: level,

            ap:
                calculateCharacterStat(
                    character.apStart,
                    character.apEnd,
                    character.maxLevel,
                    level
                ),

            hp:
                calculateCharacterStat(
                    character.hpStart,
                    character.hpEnd,
                    character.maxLevel,
                    level
                )
        });
    }

    return result;
}
