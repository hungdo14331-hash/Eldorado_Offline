
'use strict';

/**
 *
 * history :
 * 			20230711_dblee 화면마다 keyDown 함수에 테스트 코드를 넣어 두는 것을 app_test.js 파일로 정리함.
 * 							TEST 일때 동적으로 app_test.js 파일을 로딩하기 때문에 해킹 방어가 된다.
 * 							코드를 수정할 때 keyDown을 재정의 하더라도 분석이 어렵거나 등 수정이 어려움을 해결함.
 */

var bsdApp = bsdApp || {};

bsdApp.app_test = (function(){

	var api = {};
	api.name = "app_test";

	// 특정 키를 여러번 눌러서 체크 하기 위해서 사용하는 변수
	var sKey = "";
	//var TEST_KEY = '1111525522229';
	var TEST_STATE = true;
	var TEST_KEY = '45760';
	var AUTO_TEST_KEY2 = '45765';	//since 2018.01.10

	var autoTestInterval = null;	//since 2018.01.10
	var enableMenu = 0;
	var menuEl = null;

	/**************************************************************
	 * 다른 곳에 포팅을 하게 되면 아래 변수들은 수정해야 함.
	 * @type {[type]}
	 **************************************************************/

	var log_color_yellow = "text-shadow: #FC0 1px 0 10px;";
	var log_color_green = "color: green;";
	var log_color_blue = "color: blue;";
	var log_color_red = "color: red;";


	var d;
	var Dom = null;

	var oCom = null;

	var enableInit = false;	// 두번 init 하지 않기 위해서..
	/**
	 * 초기화 함수.
	 * 실행 조건문을 settings.appRelease 의 RELEASE_MODE 대신 settings.debugMenuOnOff 값으로 변경함.
	 * @return {[type]} [description]
	 */
	api.init = function() {
		enableInit = (gTARGET_PLATFORM == gPLATFORM.TOSS && util_fun.dbl.getDevice() !== util_fun.dbl.PC) ? true : false; // 20251212_dblee TOSS 플랫폼 구현(202512121318)

		if (enableInit) return;
		enableInit = true;
		initEventListener();

		oCom = {};

		initData();
		// 20240820_dblee_1608 app_test - 빨리 실행이 되어서 제대로 값을 못 읽어 옴. 그래서 2초 지연 줌
		setTimeout(function() {
			showCheatCode();
		}, 2000)

		setInterval(function() {
			addCheatList();
        }, 200);

	}

	var initData = function() {

	}



	/**
	 * key down 이벤트가 발생할 떄 마다 이 함수가 호출이 된다.
	 * @param  {[type]} event [description]
	 * @return {[type]}       [description]
	 */
	function onKeydown (event) {
		if (!TEST_STATE) return;
		if(gAPP_RELEASE !== "TEST") return;
        var keyCode = event.keyCode;

        if (keyCode >= 37 && keyCode <= 40 || keyCode == 13 ) return;

        console.log("%c "+api.name+"]  onKeydown  keyCode:"+keyCode, log_color_green);

        if (enableMenu  == 1) {
            keyDownMenu(keyCode);
        } else {
            checkTestKey(keyCode);
        }

        onAction(keyCode);

	}

	/**
	 * 각 화면별 테스트 키가 틀리니 화면별 만들어 두면 좋고
	 * 키 하나 마다 동작이 틀려서 onAction 이라고 함수로 묶음
	 *
	 * 주의 사항 !!!!!
	 * x, m은 사용하지 말것.  지정된 값임.
	 *
	 * KeyDefine.SHOWMETHEMONEY	= 83; //"s"
	 * KeyDefine.LEVELUP			= 76; //"l"
	 * KeyDefine.GAMESPEED1		= 81; //"q"
	 * KeyDefine.GAMESPEED2		= 87; //"w"
	 * KeyDefine.GAMESPEED3		= 69; //"e"
	 * KeyDefine.OPENSTAGE			= 79; //"o"
	 * KeyDefine.UPGRADE			= 85; //"u"
	 * KeyDefine.GAMEINIT			= 48; //0
	 * KeyDefine.DEBUG				= 68; //"d"
	 * KeyDefine.EXIT_TEST			= 88; //"x"
	 * KeyDefine.GAMEVICTORY		= 86; //'v' 강제로 게임에서 이겼다 할때.
	 * KeyDefine.GAMEFAIL			= 70; //'f' 강제로 게임졌다고 할 경우.
	 *
	 * @param  {[type]} keyCode [description]
	 * @return {[type]}         [description]
	 */
	function onAction(keyCode) {
		console.log("%c "+api.name+"] onAction  keyCode:"+keyCode+"  gAPP_RELEASE:"+gAPP_RELEASE, log_color_green);
		console.log("%c "+api.name+"] onAction  g_sceneinfo.cur_scene:"+g_sceneinfo.cur_scene, log_color_green);

		if (keyCode == 221) { // ]
			if ($('#cheat_code_box').css('display') == 'grid')
				$('#cheat_code_box').hide();
			else
				$('#cheat_code_box').show();
		} else if (keyCode == 21) { // 한/영 키

			USER.lang++;
			if (USER.lang > LANG.PORTUGAL) USER.lang = 1;
			LANG.init();

			if (USER.lang == 1)
				utilNotice(" 한글 언어 설정 ", 2);
			else if (USER.lang == 2)
				utilNotice(" ENGLISH 언어 설정 ", 2);
			else if (USER.lang == 3)
				utilNotice(" VIETNAM 언어 설정 ", 2);
			else if (USER.lang == 4)
				utilNotice(" SPAIN 언어 설정 ", 2);
			else if (USER.lang == 5)
				utilNotice(" RUSSIA 언어 설정 ", 2);
			else if (USER.lang == 6)
				utilNotice(" PORTUGAL 언어 설정 ", 2);
		}



		switch (g_sceneinfo.cur_scene)
		{
			case gS_EVENT:
                on_action_event (keyCode);
			break;
			case gS_MAINMENU:
				// on_action_mainmenu (keyCode);
				on_action_mainmenu_char_8 (keyCode); // 8성 추가

			break;
			case gS_SELECTSTAGE:
				on_action_select_stage(keyCode);
			break;
			case gS_PACKAGE_STORE:
				on_action_package_store(keyCode);
			break;
			case gS_CLOUD_GARDEN:
				on_action_cloud_game(keyCode);
			break;
			case gS_DAYDUNGEON:
				on_action_daydungeon_game(keyCode);
			break;
			case gS_GAME:
				on_action_game(keyCode);
			break;
			case gS_DAYDUNGEON_SELECT:
				on_action_daydungeon_select(keyCode);
			break;
			case gS_BOSS:
				on_action_boss_game(keyCode);
			break;
			case gS_RANKING:
				on_action_ranking(keyCode);
			break;
			case gS_RANKING_PVP:
				on_action_ranking_pvp(keyCode);
			break;
			case gS_RANKING_BOSS:
				on_action_ranking_boss(keyCode);
			break;
			case gS_SETTING:
				on_action_settings (keyCode); // 8성 추가
			break;
			case gS_CHARBOOK_ENEMY: // 20240102_dblee 추가함
				on_action_charbook_enemy (keyCode);
			break;
			case gS_FOUR_GODS: // 20240102_dblee 추가함
				on_action_four_gods (keyCode);
			break;
			case gS_MODE_SELECT: // 20240102_dblee 추가함
				on_action_mode_select (keyCode);
			break;

		}
	}


	/**
	 * 20230919_dblee
	 * KT 셋탑에 치트키를 사용하기 위해 만든 함수이다.
	 */
	function set_tv_id()
	{
		var is_tv_id = false;
		if (is_tv_id)
			gEntrix.host_id = 'DSWLFU5SNVTNJ'; // 회사 KT 셋탑
	}
	/**
	 * 스테이지 OPEN시 스테이지 정보 값을 받아서 사용하도록 수정함.
	 */
	function get_stage_open_input()
	{
		// 사용자로부터 값을 입력받습니다
        var userInput = parseInt( prompt("스테이지 값을 입력하세요:") );

        // 입력값이 null이 아닌 경우(사용자가 입력했을 경우) 처리
        if (userInput !== null) {
            // 입력값을 알림으로 보여줍니다
            if (userInput > MAX_STAGE_NUM)
            {
            	alert("입력은 "+MAX_STAGE_NUM+"보다 작아야 합니다.");
            }
            else
            {
	            set_tv_id();
				var open = userInput;
				// alert("입력 open:"+open);
				STORAGE.data3 = [];
				for(var i=1;i<=open;i++)
				{
					STORAGE.data3[i] = "A";
				}
				STORAGE.data3[open +1]="T";
				// for(var i=open+2;i<=MAX_STAGE_NUM;i++)
				// {
				// 	STORAGE.data3[i] ="X";
				// }
				STORAGE.save_all_info_to_storage("치트키:OPENSTAGE"); //모든 정보를 sotrage에 저장한다.

				utilNotice("Test를 위해 "+open+"stage까지 열어 두었습니다. Good Game!~",1.2);
				S_MEDALPOWER.cal_power();

				if (userInput > 200)
				{
					CUR_HARD_STAGE_NUM = 201;//현재 도전중이 하드모드 스테이지 번호
					HARD_MODE_JEWEL = "1,1,1,1,1,1,1,1,1,1";//하드모드에서 획득한 보석 정보
					ServerConnection.update_HardMode_to_server("치트키:하드모드 오픈");
				}
				else
				{
					CUR_HARD_STAGE_NUM = 1;//현재 도전중이 하드모드 스테이지 번호
					HARD_MODE_JEWEL = "0,0,0,0,0,0,0,0,0,0";//하드모드에서 획득한 보석 정보
					ServerConnection.update_HardMode_to_server("치트키:하드모드 CLOSE");
				}
			}
        } else {
            alert("입력이 취소되었습니다.");
        }
	}

	// 8성 추가 테스트
	function on_action_mainmenu_char_8 (keyCode)
	{
		var temp_id = gEntrix.host_id;

		console.log("%c "+api.name+"]  on_action_mainmenu_char_8  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 65://a   php에 테스트 ID 등록 해야 함

					set_tv_id();
					for (var i = 82; i <= 94; i++)
					{
						ServerConnection.put_reward_char('CHAR','TEST[치트키]',i);
					}
					utilNotice("우편함으로 8성 캐릭터 추가 함",3.0);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);
					break;
			case 66://b  우편함으로 7성 캐릭터 추가 함
					set_tv_id();
					for (var i = 62; i <= 68; i++)
					{
						ServerConnection.put_reward_char('CHAR','TEST[치트키]',i);
					}
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',48);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',49);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',50);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',56);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',75);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',81);
					utilNotice("우편함으로 7성 캐릭터 추가 함",3.0);

					ServerConnection.put_reward_char('CHAR','TEST[치트키]',30); // 루시6성
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);
				break;
			case 67://c
					set_tv_id();
					var unit_num = 48; // 황금맨 7성
					var unit_num = 50; // 센언니 루시 7성
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);

					var unit_num = 49; // 대천사 루시 7성
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);

					// ServerConnection.put_reward_char('CHAR','TEST[치트키]',73);
					// ServerConnection.put_reward_char('CHAR','TEST[치트키]',74);

					utilNotice("우편함으로 진화용 대천사, 센언니 루시 6개 7성 캐릭터 추가 함",3.0);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);
				break;
			case KeyDefine.DEBUG: // d 테스트를 위해 debug창을 on/off한다.
					$('#LOGLOG').css({display:'block'});
					break;
			case 69: // e  구름조각 1000개 획득
					set_tv_id();
					var cloud_piece = 11;
					ServerConnection.put_reward_char('CLOUD','TEST[치트키]',cloud_piece);
					utilNotice("우편함으로 구름조각 "+cloud_piece+"개 추가 함",3.0);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);
				/*
					var order_obj = {'MODE':'ADD', 'ADD_PIECE': 1000, 'ETC': "TEST[치트키]로 1000구름조각 획득"};
					ServerConnection.edit_cloud_garden(order_obj, function(json_data) {
						// 전체 값을 받아서 넣는다.
						USER.cloud_piece = Number(json_data.tot_piece);
						S_MAINMENU.update_screen_top();
					});
				*/
					break;
			case 70: // f  BP 50개를 우편함으로
					ServerConnection.put_reward_char('BP','TEST[치트키]',50);
					utilNotice("우편함으로 BP 50개 추가 함",3.0);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);

					break;
			case 71: // g
					if (glo.APP_FEATURE.HISTORY_BACK)
					{
						glo.APP_FEATURE.HISTORY_BACK = 0;
						utilNotice("HISTORY_BACK OFF",3.0);
					}
					else
					{
						glo.APP_FEATURE.HISTORY_BACK = 1;
						utilNotice("HISTORY_BACK ON",3.0);
					}
				break;
			case 72: // h  BP 50개를 우편함으로
					set_tv_id();
					ServerConnection.put_reward_char('RUBY','TEST[치트키]',5000);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);
					ServerConnection.put_reward_char('GOLD','TEST[치트키]',1000000);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);

					break;
			case 73://i  아이템을 우편함으로 획득
					set_tv_id();
					//D
					if (0)
					{
						ServerConnection.put_reward_char('ITEM','TEST[치트키]',131);
						ServerConnection.put_reward_char('ITEM','TEST[치트키]',231);
						ServerConnection.put_reward_char('ITEM','TEST[치트키]',331);
						ServerConnection.put_reward_char('ITEM','TEST[치트키]',431);

						//C
						ServerConnection.put_reward_char('ITEM','TEST[치트키]',141);
						ServerConnection.put_reward_char('ITEM','TEST[치트키]',241);
						ServerConnection.put_reward_char('ITEM','TEST[치트키]',341);
						ServerConnection.put_reward_char('ITEM','TEST[치트키]',441);
					}
					//B
					ServerConnection.put_reward_char('ITEM','TEST[치트키]',151);
					ServerConnection.put_reward_char('ITEM','TEST[치트키]',251);
					ServerConnection.put_reward_char('ITEM','TEST[치트키]',351);
					ServerConnection.put_reward_char('ITEM','TEST[치트키]',451);
					utilNotice("우편함으로 아이템 12개 지급 .",3.0);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);
					break;
			case 82: // r  영웅 아이템 선택권을 우편함으로 (20260120_sykim 전용 아이템 구현(202601201347))
					set_tv_id();
					ServerConnection.put_reward_char('HERO_ITEM','TEST[치트키]', 0);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);
					utilNotice("우편함으로 영웅 아이템 선택권(오공/묵향) 1개 추가 함",3.0);
					break;
			case 74:// j  업적테스트
					S_MAINMENU.make_screen_top_add_ruby(1);
					save_UserInfo_after_pay_to_server(1,"업적보상모두받기(루비)");
					STORAGE.save_all_info_to_storage("업적모두받기:(루비:"+1+"개, 골드:"+utilGetNumber_withComma(0+"")+")");
					STORAGE.save_quest_to_server();
					break;
			case 75:// k  청룡 획득
					set_tv_id();
					ServerConnection.put_reward_char('CHAR','TEST[치트키]', 95);
					utilNotice("우편함으로 청룡 캐릭터 추가 함",3.0);
					ServerConnection.get_reward2_mailbox(S_MAINMENU.check_reward_mailbox);
					break;
			case KeyDefine.LEVELUP: //l
					var userInput = parseInt( prompt("사용자 레벨 값을 입력하세요(최대 160):") );
			        // 입력값이 null이 아닌 경우(사용자가 입력했을 경우) 처리
					if (userInput === null) {
							alert("입력이 취소되었습니다.");
					}
					else {
						// 입력값을 알림으로 보여줍니다
						if (userInput > 160) {
							alert("입력은 "+161+"보다 작아야 합니다.");
						}
						else {
							set_tv_id();
							if(USER.level <= DEFINE.USER_LEVEL_MAX) {
								USER.level = parseInt(userInput);
								if(USER.level >DEFINE.USER_LEVEL_MAX){USER.level=DEFINE.USER_LEVEL_MAX}
								utilNotice("Test를 위해 사용자 Level을 "+userInput+"으로 올렸습니다. 수고혀~~",1.2);
								STORAGE.save_all_info_to_storage("치트키:Level Up"); //모든 정보를 sotrage에 저장한다.
								S_MAINMENU.update_screen_top();
							}
						}
					}


					break;
			case 77: // m
					var userInput = parseInt( prompt("아군 캐릭터 번호를 입력하세요(최대 112):") );
			        // 입력값이 null이 아닌 경우(사용자가 입력했을 경우) 처리
					if (userInput === null) {
							alert("입력이 취소되었습니다.");
					}
					else {
						// 입력값을 알림으로 보여줍니다
						if (userInput > 112) {
							alert("입력은 "+112+"보다 작아야 합니다.");
						}
						else {
							set_tv_id();
							ServerConnection.put_reward_char('CHAR','TEST[치트키]',userInput);
						}
					}
					break;
			case 78: // n
					var userInput = parseInt( prompt("아이템 번호를 입력하세요 예:473 (신발,S,상)") );
			        // 입력값이 null이 아닌 경우(사용자가 입력했을 경우) 처리
					if (userInput === null) {
							alert("입력이 취소되었습니다.");
					}
					else {
						// 입력값을 알림으로 보여줍니다
						if (userInput > 745) {
							alert("입력은 "+745+"보다 작아야 합니다.");
						}
						else {
							set_tv_id();
							ServerConnection.put_reward_char('ITEM','TEST[치트키]',userInput);
						}
					}
					break;

			case KeyDefine.OPENSTAGE: //o
					set_tv_id();
					get_stage_open_input();
					break;
			case 80: // p
					var unit_num = 17; // 스마티 4성 (17)
					var unit_num = 7; // 에이스 4성
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',unit_num);
				break;
			case 81: // Q
				glo.TEST_MODE.IMG_PATH_LOCAL = (glo.TEST_MODE.IMG_PATH_LOCAL) ? 0: 1;
				if (glo.TEST_MODE.IMG_PATH_LOCAL)
					utilNotice("로컬에서 이미지 로딩 ON ", 2);
				else
					utilNotice("로컬에서 이미지 로딩 OFF ", 2);

				break;
			case KeyDefine.SHOWMETHEMONEY: //s

					ServerConnection.put_reward_char('RUBY','TEST[치트키]',100);
					ServerConnection.put_reward_char('GOLD','TEST[치트키]',10000);
					ServerConnection.put_reward_char('BP','TEST[치트키]',100);
					utilNotice("골드 10000, 루비 100개 , BP 100개를 우편함으로 지급하였습니다.",2);
					// //USER.gold = USER.gold + 100000;
					// S_MAINMENU.make_screen_top_add_gold(100000);

					// //USER.ruby = USER.ruby + 100;
					// S_MAINMENU.make_screen_top_add_ruby(100);

					// ServerConnection.add_bonus_point(100,"치트키 ");
					// USER.bonus_point = USER.bonus_point + 100;


					// utilNotice("골드 10000, 크리스탈 100개 , BP 100개 를 추가 하였습니다. 즐~게임",1.5);
					// STORAGE.save_all_info_to_storage("치트키:SHOWMETHEMONEY"); //모든 정보를 sotrage에 저장한다.
					// save_UserInfo_after_pay_to_server(100,"치트키");
					// S_MAINMENU.make_screen_top();
					break;
			case KeyDefine.UPGRADE: // "u" 버턴
					var userInput = parseInt( prompt("업그레이드 레벨 값을 입력하세요(최대 160):") );

			        // 입력값이 null이 아닌 경우(사용자가 입력했을 경우) 처리
					if (userInput !== null) {
						// 입력값을 알림으로 보여줍니다
						if (userInput > 160)
						{
							alert("입력은 "+161+"보다 작아야 합니다.");
						}
						else
						{
							set_tv_id();
							var upgrade_level = userInput;
							STORAGE.data1.upgrade[1] = upgrade_level;
							STORAGE.data1.upgrade[2] = upgrade_level;
							STORAGE.data1.upgrade[3] = 120; // 미사일 데미지증가는 Max가 120이다.
							STORAGE.data1.upgrade[4] = upgrade_level;
							STORAGE.data1.upgrade[5] = upgrade_level;
							if (gTARGET_PLATFORM == gPLATFORM.KT)
								STORAGE.data1.upgrade[6] = 12;
							else
								STORAGE.data1.upgrade[6] = 20;
							STORAGE.data1.upgrade[7] = upgrade_level; //메테오 파워
							if (upgrade_level > 120)
								STORAGE.data1.upgrade[8] = 120; //아군저장소 업
							else if (upgrade_level < 30)
								STORAGE.data1.upgrade[8] = 30; //아군저장소 업
							else
								STORAGE.data1.upgrade[8] = upgrade_level; //아군저장소 업

							if (upgrade_level > 100)
								STORAGE.data1.upgrade[9] = 100; //아이템 저장소 업
							else if (upgrade_level < 60)
								STORAGE.data1.upgrade[9] = 60; //아이템 저장소 업
							else
								STORAGE.data1.upgrade[9] = upgrade_level; //아이템 저장소 업

							MAX_OUR_TEAM_NUM_ON_SCREEN = STORAGE.data1.upgrade[6]; //이부장님 지적
							STORAGE.save_all_info_to_storage("치트키:업그레이드"); //모든 정보를 sotrage에 저장한다.
							loading_show("치트키:업그레이드", 1);

							api.remove_tower_awakening(function() {
								loading_hide("치트키:업그레이드", 1);
								USER.tower_awakening = 0;
								utilNotice("UPGRADE메뉴 모두 "+STORAGE.data1.upgrade[1]+"으로 UP 및 타워각성 초기화 ~~ good game~~^^ ",1.5);
							})
						}
					} else {
						alert("입력이 취소되었습니다.");
					}
					break;
			case 89: // "y" 버턴
					set_tv_id();
					var upgrade_level = 1;
					STORAGE.data1.upgrade[1] = upgrade_level;
					STORAGE.data1.upgrade[2] = upgrade_level;
					STORAGE.data1.upgrade[3] = 1; // 미사일 데미지증가는 Max가 120이다.
					STORAGE.data1.upgrade[4] = upgrade_level;
					STORAGE.data1.upgrade[5] = upgrade_level;
					if (gTARGET_PLATFORM == gPLATFORM.KT)
						STORAGE.data1.upgrade[6] = 10;
					else
						STORAGE.data1.upgrade[6] = 10;
					STORAGE.data1.upgrade[7] = upgrade_level; //메테오 파워
					STORAGE.data1.upgrade[8] = 1; //아군저장소 업
					STORAGE.data1.upgrade[9] = 1; //아이템 저장소 업
					MAX_OUR_TEAM_NUM_ON_SCREEN = STORAGE.data1.upgrade[6]; //이부장님 지적
					STORAGE.save_all_info_to_storage("치트키:업그레이드 초기화"); //모든 정보를 sotrage에 저장한다.
					utilNotice("UPGRADE메뉴 모두 "+STORAGE.data1.upgrade[1]+"으로~~ good game~~^^",1.5);
					break;

			case 90: // z
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',96);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',97);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',98);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',99);
					ServerConnection.put_reward_char('CHAR','TEST[치트키]',100);


				break;
			case KeyDefine.GAMEINIT: //0
					break;
			case 88: // x
					utilNotice("우편함 테스트를 위해 우편함에 보상을 지급 합니다.",3.0);

					ServerConnection.put_reward_char('GOLD','치트키 GOLD 보상',10);
					// ServerConnection.put_reward_char('BP','TEST BP 보상',5);
					// ServerConnection.put_reward_char('RUBY','TEST RUBY 보상',10);
					ServerConnection.put_reward_char('CLOUD','치트키 구름조각 보상',10);

					for(var i = 1; i <= 0;i++)
					{
						var rnd =  Math.floor(Math.random()*68 + 1); //1 ~ 100;
						utilConsoleLog("~~ 우편함에 캐릭터 보상 등록 ~~ "+rnd);
						ServerConnection.put_reward_char('CHAR','치트키 CHAR 보상',rnd);
					}
					break;
			case KeyDefine.NUM5 :
					break;
			case KeyDefine.NUM6:

					break;
			case KeyDefine.NUM9 : //테스트를 위해 100 level 클리어한 사용자 정보 가지고 오기.

					break;



		}

		gEntrix.host_id = temp_id;
	}

	/**
	 * 구름정원
	 * - 패배는 없습니다. 무조건 clear 화면으로 이동합니다. 그래서 패배 단축키 없습니다.
	 * @param  {Number} keyCode keyCode
	 */
	function on_action_cloud_game (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_boss_game  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 66: // b
				// 게임 중에 아군 무적 상태 ON
				glo.TEST_MODE.OUR_CHAR_INVINCIBLE = 1;
				utilNotice("아군 무적 상태 ON ",1.5);
				break;
			case 67: // c
				// 게임 중에 아군 무적 상태 OFF
				glo.TEST_MODE.OUR_CHAR_INVINCIBLE = 0;
				utilNotice("아군 무적 상태 OFF ",1.5);
				break;
			case 71: // g
				glo.TEST_MODE.CASTLE_OUR_INVINCIBLE = 1;
				utilNotice("아군 타워 무적 상태 ON ",1.5);
				break;
			case 72: // h
				glo.TEST_MODE.CASTLE_OUR_INVINCIBLE = 0;
				utilNotice("아군 타워 무적 상태 OFF ",1.5);
				break;

			case KeyDefine.GAMEVICTORY: //'v'  강제로 게임 win 처리 하기
					if(gAPP_RELEASE == "TEST")
					{
						clearInterval(S_CLOUD_GARDEN.timer_interval);
						S_CLOUD_GARDEN.stop_render(); // 20250312_dblee_1419 code refactoring - 애니메이션 개선함.
						ChangeScene.start(g_sceneinfo.cur_scene,gS_CLOUD_GARDEN_CLEAR,S_CLOUD_GARDEN_CLEAR);
					}
					break;
		}
	}

	function on_action_boss_game (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_boss_game  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 66: // b
				// 게임 중에 아군 무적 상태 ON
				glo.TEST_MODE.OUR_CHAR_INVINCIBLE = 1;
				utilNotice("아군 무적 상태 ON ",1.5);
				break;
			case 67: // c
				// 게임 중에 아군 무적 상태 OFF
				glo.TEST_MODE.OUR_CHAR_INVINCIBLE = 0;
				utilNotice("아군 무적 상태 OFF ",1.5);
				break;
			case 71: // g
				glo.TEST_MODE.CASTLE_OUR_INVINCIBLE = 1;
				utilNotice("아군 타워 무적 상태 ON ",1.5);
				break;
			case 72: // h
				glo.TEST_MODE.CASTLE_OUR_INVINCIBLE = 0;
				utilNotice("아군 타워 무적 상태 OFF ",1.5);
				break;
			case KeyDefine.GAMEVICTORY: //'v'  강제로 게임 win 처리 하기
				clearInterval(S_BOSS.timer_interval);
				S_BOSS.stop_render(); // 20250312_dblee_1419 code refactoring - 애니메이션 개선함.

				if (gTARGET_PLATFORM == gPLATFORM.LGWEBOS_TV)
				{
					$('#S_BOSSCLEAR_div').css({'display': "block"});
					S_BOSSCLEAR.init();
				}
				else if (gTARGET_PLATFORM == gPLATFORM.TIZEN_TV || gTARGET_PLATFORM == gPLATFORM.SSBR || gTARGET_PLATFORM === gPLATFORM.ENTRIX_CNM)
				{
					ChangeScene.start(g_sceneinfo.cur_scene,gS_BOSSCLEAR,S_BOSSCLEAR);
				}
				break;
			case KeyDefine.GAMEFAIL : //'f' 강제로 게임 fail 처리하기
                S_BOSS.end_boss_hp = S_BOSS.start_boss_hp;  // 추가: end_boss_hp 강제 초기화
				CASTLE_OUR.cur_hp = 0;
				S_BOSS.ourCastle_destroyAni();
				break;
			case 192://  '   버튼   미사일 발사 버튼
				if(USER.missile_cur_tick >= USER.missile_full_tick) // 미사일 게이지가 다 차면
				{
					S_GAME.effect_del('game_ui_missile');//effect 효과도 지워라.

					//S_BOSS.fireRaser(); //발사하라. ==> 발사 프레임에서 3~4 프레임 발사때 하기위해 이동함.
					USER.missile_cur_tick = 0; //그리고 게이지를 비워라.
					CASTLE_OUR.mode = MODE.ATTACK;

					S_GAME.bottom_ui.reder_missile_gage(); //미사일을 게이지 검정색으로 모두 덮어 재 사용 못하게 한다.
				}
				break;
		}
	}

	function on_action_daydungeon_game (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_daydungeon_game  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{

			case 66: // b
				// 게임 중에 아군 무적 상태 ON
				glo.TEST_MODE.OUR_CHAR_INVINCIBLE = 1;
				utilNotice("아군 무적 상태 ON ",1.5);
				break;
			case 67: // c
				// 게임 중에 아군 무적 상태 OFF
				glo.TEST_MODE.OUR_CHAR_INVINCIBLE = 0;
				utilNotice("아군 무적 상태 OFF ",1.5);
				break;
			case 68: // d
				// 게임 중에 적군 무적 상태 ON
				glo.TEST_MODE.YOUR_CHAR_INVINCIBLE = 1;
				utilNotice("적군 무적 상태 ON ",1.5);
				break;
			case 69: // e
				// 게임 중에 적군 무적 상태 OFF
				glo.TEST_MODE.YOUR_CHAR_INVINCIBLE = 0;
				utilNotice("적군 무적 상태 OFF ",1.5);
				break;
			case 71: // g
				glo.TEST_MODE.CASTLE_OUR_INVINCIBLE = 1;
				utilNotice("아군 타워 무적 상태 ON ",1.5);
				break;
			case 72: // h
				glo.TEST_MODE.CASTLE_OUR_INVINCIBLE = 0;
				utilNotice("아군 타워 무적 상태 OFF ",1.5);
				break;

			case 74: // j
				// 게임 중에 적군 무적 상태 OFF
				glo.TEST_MODE.CASTLE_YOUR_INVINCIBLE = 1;
				utilNotice("적군 타워 무적 상태 ON ",1.5);
				break;
			case 75: // k
				// 게임 중에 적군 무적 상태 OFF
				glo.TEST_MODE.CASTLE_YOUR_INVINCIBLE = 0;
				utilNotice("적군 타워 무적 상태 OFF ",1.5);
				break;
			case 76: // l
				glo.TEST_MODE.DISABLE_CASTLE_YOUR_FIRE = 1;
				utilNotice("적군 타워 미사일 발사 정지 ON",1.5);
				break;
			case 77: // m
				glo.TEST_MODE.DISABLE_CASTLE_YOUR_FIRE = 0;
				utilNotice("적군 타워 미사일 발사 정지 OFF",1.5);
				break;
			case KeyDefine.GAMEVICTORY: //'v'  강제로 게임 win 처리 하기
				clearInterval(S_BOSS.timer_interval);
				S_BOSS.stop_render(); // 20250312_dblee_1419 code refactoring - 애니메이션 개선함.
				if (gTARGET_PLATFORM == gPLATFORM.LGWEBOS_TV)
				{
					$('#S_DAYDUNGEON_CLEAR_div').css({'display': "block"});
					S_DAYDUNGEON_CLEAR.init();
				}
				else if (gTARGET_PLATFORM == gPLATFORM.TIZEN_TV || gTARGET_PLATFORM == gPLATFORM.SSBR || gTARGET_PLATFORM === gPLATFORM.ENTRIX_CNM)
				{
					ChangeScene.start(g_sceneinfo.cur_scene,gS_DAYDUNGEON_CLEAR,S_DAYDUNGEON_CLEAR);
				}
				break;
			case KeyDefine.GAMEFAIL : //'f' 강제로 게임 fail 처리하기
				CASTLE_OUR.cur_hp = 0;
				S_DAYDUNGEON.ourCastle_destroyAni();
				break;
			case 192://  '   버튼   미사일 발사 버튼
				if(USER.missile_cur_tick >= USER.missile_full_tick) // 미사일 게이지가 다 차면
				{
					S_GAME.effect_del('game_ui_missile');//effect 효과도 지워라.

					//S_DAYDUNGEON.fireRaser(); //발사하라. ==> 발사 프레임에서 3~4 프레임 발사때 하기위해 이동함.
					USER.missile_cur_tick = 0; //그리고 게이지를 비워라.
					CASTLE_OUR.mode = MODE.ATTACK;

					S_GAME.bottom_ui.reder_missile_gage(); //미사일을 게이지 검정색으로 모두 덮어 재 사용 못하게 한다.
				}
				break;
		}
	}
	function on_action_game (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_game  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{

			case KeyDefine.NUM6:
			case KeyDefine.NUM7:
			case KeyDefine.NUM8:
			case KeyDefine.NUM9:
			case KeyDefine.NUM0:
				if (S_GAME.is_pvp_mode())
				{
					USER_NPC.focus = keyCode - 53;
					if (USER_NPC.focus < 0) USER_NPC.focus = 5; // 0은 keycode 48이여서 예외처리함.
					if(USER_NPC.focus <= USER_NPC.num)
					{
						var unit_num = USER_NPC['char'][USER_NPC.focus].unit_num;
						S_GAME.addYourUnit_NPC(unit_num);
						S_GAME.acc_your_num++;
					}
				}
				break;
			case 192://  '   버튼   미사일 발사 버튼
					if(USER.missile_cur_tick >= USER.missile_full_tick) // 미사일 게이지가 다 차면
					//if(1) //미사일 테스트를 위해
					{
						S_GAME.effect_del('game_ui_missile');//effect 효과도 지워라.

						//S_GAME.fireRaser(); //발사하라. ==> 발사 프레임에서 3~4 프레임 발사때 하기위해 이동함.
						USER.missile_cur_tick = 0; //그리고 게이지를 비워라.
						CASTLE_OUR.mode = MODE.ATTACK;

						S_GAME.bottom_ui.reder_missile_gage(); //미사일을 게이지 검정색으로 모두 덮어 재 사용 못하게 한다.
					}
				break;
			case 65: // a
				// 하늘 정원에서 다음 웨이브 이동
				if (S_GAME.ranking_mode == 1)
				{
					glo.TEST_MODE.NEXT_WAVE_GO = 1;
					// utilNotice("다음 웨이브로 이동 합니다. ",1.5);
					S_GAME.nextWaveGo();
				}
				break;
			case 66: // b
				// 게임 중에 아군 무적 상태 ON
				glo.TEST_MODE.OUR_CHAR_INVINCIBLE = 1;
				utilNotice("아군 무적 상태 ON ",1.5);
				break;
			case 67: // c
				// 게임 중에 아군 무적 상태 OFF
				glo.TEST_MODE.OUR_CHAR_INVINCIBLE = 0;
				utilNotice("아군 무적 상태 OFF ",1.5);
				break;
			case 68: // d
				// 게임 중에 적군 무적 상태 ON
				glo.TEST_MODE.YOUR_CHAR_INVINCIBLE = 1;
				utilNotice("적군 무적 상태 ON ",1.5);
				break;
			case 69: // e
				// 게임 중에 적군 무적 상태 OFF
				glo.TEST_MODE.YOUR_CHAR_INVINCIBLE = 0;
				utilNotice("적군 무적 상태 OFF ",1.5);
				break;



			case KeyDefine.GAMEFAIL : //'f' 강제로 게임 fail 처리하기
						CASTLE_OUR.cur_hp = 0;
						S_GAME.ourCastle_destroyAni();
					break;
			case 71: // g
				// 게임 중에 적군 무적 상태 OFF
				glo.TEST_MODE.CASTLE_OUR_INVINCIBLE = 1;
				utilNotice("아군 타워 무적 상태 ON ",1.5);
				break;
			case 72: // h
				// 게임 중에 적군 무적 상태 OFF
				glo.TEST_MODE.CASTLE_OUR_INVINCIBLE = 0;
				utilNotice("아군 타워 무적 상태 OFF ",1.5);
				break;
			case 73: // i 누르면 자동으로 캐릭터 , 미사일을 발사하도록 하자
						var loop_function = function()
						{
							if( g_sceneinfo.cur_scene == gS_GAME)
							{//게임 화면 일때만 타이머를 돌리자
								if(S_GAME.focus <= 6)
									S_GAME.focus++;
								else
									S_GAME.focus = 1;

								S_GAME.focusRun();
								setTimeout(loop_function, 50);
							}
						}
						loop_function();
					break;
			case 74: // j
				glo.TEST_MODE.CASTLE_YOUR_INVINCIBLE = 1;
				utilNotice("적군 타워 무적 상태 ON ",1.5);
				break;
			case 75: // k
				glo.TEST_MODE.CASTLE_YOUR_INVINCIBLE = 0;
				utilNotice("적군 타워 무적 상태 OFF ",1.5);
				break;
			case 76: // l
				glo.TEST_MODE.DISABLE_CASTLE_YOUR_FIRE = 1;
				utilNotice("적군 타워 미사일 발사 정지 ON",1.5);
				break;
			case 77: // m
				glo.TEST_MODE.DISABLE_CASTLE_YOUR_FIRE = 0;
				utilNotice("적군 타워 미사일 발사 정지 OFF",1.5);
				break;

			case 80: // p
				glo.TEST_MODE.GAME_PAUSED ? glo.TEST_MODE.GAME_PAUSED = 0 : glo.TEST_MODE.GAME_PAUSED = 1;
				utilNotice(" GAME_PAUSED: "+glo.TEST_MODE.GAME_PAUSED,3.0);
				break;
			case KeyDefine.GAMESPEED1: // q (81) 1배속
						utilConsoleLog("================1배속");
						TIMER_INTERVAL = 67;

						S_GAME.autoYourTeamManager_timeout();

						document.getElementById("temp_text").innerHTML = "=== 1배속 게임 ====";
						$('#temp_text').css({ 'display':'block',
												left:100 + 'px'  ,
												top: 140 + 'px',
												position: 'absolute',
												width : 1000 + 'px',
												height : 100 + 'px',
												'font-size'  : '50rem',
												'text-align' : 'center',
												//background : 'yellow',
												'color' : 'white'
											});
						setTimeout(function() {
												$('#temp_text').css({ 'display':'none'});
												},2000);
						break;
			case 82: // r
					utilNotice(" TEST 게임이 재시작되었습니다.", 1.5);
					S_GAME.resume();
					break;
			case KeyDefine.GAMEVICTORY: // v  강제로 게임 win 처리 하기
						CASTLE_YOUR.cur_hp = 0;
						S_GAME.win(); //이겼으니 계산할거 계산해야 한다.
						S_GAME.yourCastle_destroyAni(); //적군성 터지는 애니메이션 하고 STAGECLEAR화면 나타나라.
					break;
            case 90: // z  강제로 PVP 클래식 무승부 처리 하기
					// 20260529_dblee PVP 클래식 구현 (202605291048) 무승부 치트키 - 타워 HP를 동일하게 맞춰 무승부(RESULT_TYPE.D) 결과 화면으로 이동
					if (S_GAME.is_pvp_classic_mode() || S_GAME.is_pvp_classic_mode())
					{
						CASTLE_OUR.cur_hp = CASTLE_YOUR.cur_hp; // 무승부 조건(아군/적군 타워 HP 동일) 맞추기
						S_GAME.end_flag = 1;
						S_GAME.finish_game_ani();
						setTimeout(function()
						{
							S_GAME.end();
							S_GAME.end_memory_free(); //memory free
							$('#Img_GA_castle_destroy_effect').css({display:'none'});
							glo.pvp.set_game_result(glo.pvp.RESULT_TYPE.D); //무승부로 결과 설정
							glo.pvp.goto_result_scene(); //클래식 결과 화면(S_STAGECLEAR)으로 이동
						}, 2000);
					}
					else
					{
						utilNotice(" PVP 클래식 게임에서만 사용 가능한 치트키 입니다.", 2.0);
					}
					break;
			case KeyDefine.GAMESPEED2: // w
						utilConsoleLog("================2배속");
						TIMER_INTERVAL = 34;
						S_GAME.autoYourTeamManager_timeout();
						document.getElementById("temp_text").innerHTML = "=== 2배속 게임 ====";
						$('#temp_text').css({ 'display':'block',
												left:100 + 'px'  ,
												top: 140 + 'px',
												position: 'absolute',
												width : 1000 + 'px',
												height : 100 + 'px',
												'font-size'  : '50rem',
												'text-align' : 'center',
												//background : 'yellow',
												'color' : 'white'
											});
						setTimeout(function() {
												$('#temp_text').css({ 'display':'none'});
												},2000);
						break;

		}
	}
	// gS_DAYDUNGEON_SELECT
	function on_action_daydungeon_select (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_daydungeon_select  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case KeyDefine.NUM1:

					if(S_DAYDUNGEON_SELECT.cur_day < 7)
						S_DAYDUNGEON_SELECT.cur_day++;
					else
						S_DAYDUNGEON_SELECT.cur_day = 1;

					S_DAYDUNGEON_SELECT.make_screen_center();
				break;
		}
	}

	// gS_RANKING_PVP
	function on_action_ranking_pvp (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_ranking_pvp  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 65: // a
				glo.TEST_MODE.TEST_PVP_MANUAL_UNIT = 0;
				utilNotice(" 자동으로 적군이 출전됩니다.", 1.5);
				break;
			case 66: // b
				glo.TEST_MODE.TEST_PVP_MANUAL_UNIT = 1;
				utilNotice(" 수동으로 적군이 출전됩니다.", 1.5);
				break;
			case 77: // m
				glo.TEST_MODE.TEST_PVP_MIRROR = 1;
				utilNotice(" 거울 PVP ON:  아군 출전 캐릭터와 동일한 캐릭터로 상대방 출전",3.0);
				break;
			case 78: // n
				glo.TEST_MODE.TEST_PVP_MIRROR = 0;
				utilNotice(" 거울 PVP OFF:  LIVE 상대방 출전",3.0);
				break;

		}
	}

	// 하늘정원
	function on_action_ranking (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_ranking  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 65: // a
				// 하늘 정원에서 다음 웨이브 이동
				var userInput = parseInt( prompt("도전할 웨이브 단계 :") );
		        // 입력값이 null이 아닌 경우(사용자가 입력했을 경우) 처리
		        if (userInput === null) {
		        	 alert("입력이 취소되었습니다.");
		        }
		        else {
		        	if (parseInt(userInput) > 0)
		        	{
			            // 입력값을 알림으로 보여줍니다
			           	set_tv_id();
						USER.clear_wave = parseInt(userInput) -1; // 클리어 한 웨이브
						RANKING_STAGE_DESIGN.wave = parseInt(userInput) // 도전 웨이브
						USER.score = USER.score +RANKING_STAGE_DESIGN.wave*RANKING_STAGE_DESIGN.wave*20;
						put_scorewave_to_server(RANKING_STAGE_DESIGN.wave,USER.score); //사용자의 wave clear한 기록을 server에 남길지 말지를 던져 본다.
					}
					else {
						alert("1 이상 숫자만 입력이 가능합니다.");
					}

		        }
				break;
		}
	}

	// 하늘정원
	function on_action_ranking_boss (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_ranking_boss  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 77: // m
					glo.TEST_MODE.BOSS_ENTER = 1;
					utilNotice("월드 보스 입장 ON.",2.0);
					break;
			case 78: // n
					glo.TEST_MODE.BOSS_ENTER = 0;
					utilNotice("월드 보스 입장 OFF.",2.0);
					break;
		}
	}

	function on_action_settings (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_settings  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 65://a   아군도감캐릭터 ALL 적용
					USER.charbook_ally_list = "";
					for (var i = 1; i <=MAX_OUR_TEAM_NUM; i++)
					{
						if (i == MAX_OUR_TEAM_NUM)
							USER.charbook_ally_list += i;
						else
							USER.charbook_ally_list += i+",";
					}

					utilNotice("아군도감캐릭터 ALL 적용 함",3.0);
					break;
			case 66://b
				utilNotice("아군도감캐릭터 ALL 미적용은 초기화 하세요",3.0);
				break;
			case 67://c   적군도감캐릭터 ALL 적용
					USER.charbook_enemy_list  = "";
					for (var i = 1; i <=MAX_YOUR_TEAM_NUM; i++)
					{
						if (i == MAX_YOUR_TEAM_NUM)
							USER.charbook_enemy_list  += i;
						else
							USER.charbook_enemy_list  += i+",";
					}
					utilNotice("적군도감캐릭터 ALL 적용 함",3.0);
					break;
			case 68://d
				USER.charbook_enemy_list  = "";
				S_CHARBOOK_ENEMY.char_book_arrar = [];
				utilNotice("적군도감캐릭터 ALL 미적용 함",3.0);
				break;
			case 69://e
				delete_user_in_server(function () {
					location.reload(true);
				}); // server에서 host_id를 삭제 하라.
				utilNotice("게임 데이터를 초기화 합니다.",3.0);
				break;
		}
	}
	// 20240102_dblee 추가함
	function on_action_charbook_enemy (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_charbook_enemy  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case KeyDefine.NUM0:
			case KeyDefine.NUM1:
			case KeyDefine.NUM2:
			case KeyDefine.NUM3:
			case KeyDefine.NUM4:
			case KeyDefine.NUM5:
			case KeyDefine.NUM6:
			case KeyDefine.NUM7:
			case KeyDefine.NUM8:
			case KeyDefine.NUM9:
				glo.fun.set_enemy_ap_hp( (keyCode -  KeyDefine.NUM0)/10 );
				utilNotice("적군 (81~90) AP와 HP 값이 "+ (keyCode -  KeyDefine.NUM0) *10  +"% 만큼 적용되었습니다", 2);
				break;

		}
	}


	function on_action_select_stage (keyCode)
	{
		switch(keyCode)
		{
			case 65: // a

				if (glo.TEST_MODE.ONE_ENEMY_DEPLOYED)
				{
					glo.TEST_MODE.ONE_ENEMY_DEPLOYED = 0;
					utilNotice("적군 한마리 출전 OFF ", 2);
				}
				else
				{
					glo.TEST_MODE.ONE_ENEMY_DEPLOYED = 1;
					utilNotice("적군 한마리 출전 ON ", 2);
				}

				break;
			case 66: // b
				loading_show("", 1);
				ServerConnection.delete_stage_run_count(function() {
					loading_hide("", 1);
					S_SELECTSTAGE.count_arr = {};
					S_SELECTSTAGE.count_arr['stage_245'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_250'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_255'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_260'] = {count: 0, max: 5};

					S_SELECTSTAGE.count_arr['stage_265'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_270'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_275'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_280'] = {count: 0, max: 5};

					S_SELECTSTAGE.count_arr['stage_285'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_290'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_295'] = {count: 0, max: 5};
					S_SELECTSTAGE.count_arr['stage_300'] = {count: 0, max: 5};
				});

				break;
		}
	}
	// gS_PACKAGE_STORE
	function on_action_package_store (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_package_store  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 68: // d
				delete_pingback();
				break;
			case 80: // p

				if (glo.TEST_MODE.TEST_CVS_PAYMENT)
				{
					glo.TEST_MODE.TEST_CVS_PAYMENT = 0;
					utilNotice("결제 테스트 성공 OFF ", 2);
				}
				else
				{
					glo.TEST_MODE.TEST_CVS_PAYMENT = 1;
					utilNotice("결제 테스트 성공 ON ", 2);
				}

				break;
			case 81: // q

				window.g.MONTH_MAX_PAYMENT = 100000000;
				utilNotice("결제 한도 1억 상향 ", 2);

				break;
		}
	}
    function on_action_event(keyCode) {
        console.log("%c " + api.name + "]  on_action_package_store  keyCode:" + keyCode, log_color_green);
        switch (keyCode) {
            case 68: // d
                delete_pingback();
                break;
            case 80: // p

                if (glo.TEST_MODE.TEST_CVS_PAYMENT) {
                    glo.TEST_MODE.TEST_CVS_PAYMENT = 0;
                    utilNotice("결제 테스트 성공 OFF ", 2);
                }
                else {
                    glo.TEST_MODE.TEST_CVS_PAYMENT = 1;
                    utilNotice("결제 테스트 성공 ON ", 2);
                }

                break;
            case 81: // q

                window.g.MONTH_MAX_PAYMENT = 100000000;
                utilNotice("결제 한도 1억 상향 ", 2);

                break;
        }
    }

	// 사방신
	function on_action_four_gods (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_four_gods  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case 65: // a
				var obj = {
					MODE: "UPDATE_139",
					TYPE: 1
				}
				ServerConnection.dragon_info_cheat(obj, null);
				utilNotice("사방신 게이지 139로 업데이트", 2);
				break;
		}
	}
	function on_action_mode_select (keyCode)
	{
		console.log("%c "+api.name+"]  on_action_mode_select  keyCode:"+keyCode, log_color_green);
		switch(keyCode)
		{
			case KeyDefine.OPENSTAGE: // o
				set_tv_id();
				// 사용자로부터 값을 입력받습니다
		        var userInput = parseInt( prompt("하드 모드 스테이지 값을 입력하세요:") );

		        // 입력값이 null이 아닌 경우(사용자가 입력했을 경우) 처리
		        if (userInput !== null) {
		            // 입력값을 알림으로 보여줍니다
		            if (userInput > 200)
		            {
		            	alert("입력은 "+200+"보다 작아야 합니다.");
		            }
		            else
		            {
			            set_tv_id();
						var open = userInput;
						utilNotice("Test를 위해 "+open+"stage까지 열어 두었습니다. Good Game!~",1.2);

						CUR_HARD_STAGE_NUM = open;//현재 도전중이 하드모드 스테이지 번호
						HARD_MODE_JEWEL = "0,0,0,0,0,0,0,0,0,0";//하드모드에서 획득한 보석 정보
						if (open == 200)
						{
							CUR_HARD_STAGE_NUM = 201;
							HARD_MODE_JEWEL = "1,1,1,1,1,1,1,1,1,1";//하드모드에서 획득한 보석 정보
						}
						ServerConnection.update_HardMode_to_server("치트키:하드모드 오픈");
					}
		        } else {
		            alert("입력이 취소되었습니다.");
		        }
				break;
		}
	}

    // KT  공식 테스트 메뉴 TEST_KEY 45760
    function keyDownMenu(keyCode) {


    }

    /**
     * 1초 마다 실행되게 한다.
     * @return {[type]} [description]
     * @since 2018.01.10	생성함
     */
    function autoTest() {


    }

    function checkTestKey(keyCode) {
        var num;
		// 숫자 0 ~ 9
		if (keyCode >= 48 && keyCode <= 57) {
			 num = keyCode - 48;
			parseKeyCode(num);
		} else {
			sKey   = "";
		}
    }

	/**
	 * 설정한 키 값이 맞나 안맞나 확인 하는 함수
	 * @param  {[type]} num [description]
	 * @return {[type]}     [description]
	 */
	function parseKeyCode(num) {
		sKey = sKey + String(num);
		if (sKey == TEST_KEY) {
            if (menuEl == null) {
                showMenu();
            } else {
                menuEl.style.display = 'block';
                enableMenu = 1;
            }
        } else if (sKey == AUTO_TEST_KEY2) {	//since 2018.01.10
        	clearInterval(autoTestInterval);
        	autoTestInterval = setInterval(function() {
        		autoTest();
        	}, 2000);
		}
	}

    /**
     * 메뉴 팝업창을 띄우자.
	 * KT  공식 테스트 메뉴 TEST_KEY 45760
     * @return {[type]} [description]
     */
    function showMenu() {
        enableMenu = 1;
        var tag = {};
        var name = fileName +'_';
        tag.bg = name+'bg';
        var divStr = '<div id="'+tag.bg+'" >'
                +'<P style="text-align:center;">테스트 APP</P></br>'
                +'<li>오광전맞고(리모콘 1)</li>'
                +'<li>AirForce2020(리모콘 2)</li>'
                +'<li>광고테스트(리모콘 3)</li>'
                +'<li>부싯돌오목(리모콘 4)</li>'
                +'<BR><li>닫기 (리모콘 9)</li>'
            +'</div>';
        document.body.innerHTML += divStr;
        var oLi = document.querySelectorAll('body div li');
        for (var i = 0; i < oLi.length; i++) {
            oLi[i].style.padding = '3px';
        }
        var oEl = document.querySelector('#'+tag.bg);
        oEl.style.position = 'absolute';
        oEl.style.display = 'block';
        oEl.style.left = 540+'px';
        oEl.style.top = 200+'px';
        oEl.style.width = 200 +'px';
        oEl.style.height = 300 +'px';
        oEl.style.background  = 'white';
        oEl.style.padding  = '10px';
        oEl.style.zIndex  = '99';

        menuEl = oEl;

    }

    function showCheatCode() {

    	var divStr = '<div id="cheat_code_box" >'
					+'</div>';

		var div_body = document.getElementById('div_body');
		var rect = div_body.getBoundingClientRect();
		var div_body_top = rect.top;
		var div_body_height = rect.height + 20; // 20 만큼 갭을 줌

		document.body.innerHTML += divStr;

		// 20240820_dblee_1609 app_test - cheat_code_box의 top 위치를 플랫폼에 따라 동적으로 적용
		var crm_top = div_body_top + div_body_height;
		var crm_left = '10px';
		if (glo.fun.is_glo_platform()) {
			crm_top = 10;
			crm_left = '50%';
		}
		else // 20241031_dblee 조건문 제거함
			crm_top = 750;

		$('#cheat_code_box').css({
			left : crm_left,
			// left : '10px',
			// top : (div_body_top+div_body_height)+'px',
			top : crm_top+'px',
			// transform: 'translateX(-50%)', /* 중앙 정렬 보정 */
			width : '1000px',
			height : '200px',
			'background-color': 'white',
			border: '2px solid red', /* 테두리 */
		    'overflow-y': 'auto', /* 내용이 넘칠 경우 스크롤 */
		    padding: '10px',
		    'box-sizing': 'border-box',
		    display: 'grid',
		    'grid-template-columns': 'repeat(3, 1fr)', /* 3열 그리드 */
		    'gap': '10px', /* 그리드 간격 */
		    'z-index': 999, /* 그리드 간격 */
			position: 'absolute'
		});
		if (glo.fun.is_glo_platform()) $('#cheat_code_box').css({transform: 'translateX(-50%)'}); /* 중앙 정렬 보정 */

		var cheatSheet = document.getElementById('cheat_code_box');
		// 치트키 데이터 배열
		var cheats = [
		  	' ] : 창 닫기/열기',
		  	'RED 키 : 키패드 1/F1',
			'BLUE 키 : 키패드 4/F4',
			'BACK 키 : ` (숫자 1 왼쪽 키)',
			'메인화면 a : 8성 캐릭터 획득',
			'메인화면 b : 7성 캐릭터 획득',
			'메인화면 c : 센언니/대천사 루시 7성 6개 캐릭터 획득',
			'메인화면 e : 구름조각 11개 획득',
			'메인화면 f : BP 50개 획득',
			'메인화면 h : 루비 5천개, 골드 100만개 획득',
			'메인화면 i : 아이템 B,C,D 획득',
			'메인화면 l : 사용자 레벨 업',
			'메인화면 m : 보스진입가능',
			'메인화면 n : 보스진입불가능',
			'메인화면 o : 260 스테이지까지 OPEN',
			'메인화면 p : 스마티 4성 7개',
			'메인화면 s : 돈좀 줘',
			'메인화면 u : 업그레이드 및 타워각성 제거',
			'메인화면 r : 영웅 선택권 획득',
			'상점 p :  결제 성공 ON/OFF',
			'게임화면 b :  다음 웨이브',
			'게임화면 c :  아군 무적 ON/OFF',
			'게임화면 v :  게임승리',
			'게임화면 f : 게임 패배',
			'요일던전랭킹화면 1 : 요일별 진입 가능',
			'PVP랭킹화면 m: 거울 PVP ON',
			'PVP랭킹화면 n: 거울 PVP OFF',
			'기타화면 a : 아군도감캐릭터ALL적용',
			'기타화면 b : 아군도감캐릭터 초기화',
			'기타화면 c : 적군도감캐릭터 ALL 적용',
			'기타화면 d : 적군도감캐릭터 ALL 미적용',
			'기타화면 e : 게임 데이터를 초기화'
		];

		for (var i = 0; i < cheats.length; i++) {
			var p = document.createElement('p'); // 새 p 요소 생성
			p.textContent = cheats[i]; // 텍스트 콘텐츠 추가
			cheatSheet.appendChild(p); // cheatSheet div에 p 요소 추가

		}
	}

    /**
     * Select Stage 화면에서 치트키 리스트 정보
     * @since 20250821_dblee_1516 혼돈 행성 281 ~ 300 Stage
     */
    function addCheatList_select_stage()
    {
    	return [
		  	' ] : 창 닫기/열기',
		  	'키패드 1/F1 : 리모컨의 RED 키',
			'키패드 4/F4 : 리모컨의 BLUE 키',
			'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
			' a :  적군 한마리만 출전 On/Off',
			' b :  오늘 날짜의 스테이지 횟수 정보 삭제',
		];
    }

    var cur_scene_name = "";
    function addCheatList() {
    	var cheatCodeBox  = document.getElementById('cheat_code_box');
    	if (!cheatCodeBox) return;
    	if (cur_scene_name == g_sceneinfo.cur_scene) return;

    	cur_scene_name = g_sceneinfo.cur_scene;

    	// 'cheat_code_box'의 자식 요소를 지운다.
    	while (cheatCodeBox.firstChild) {
 			cheatCodeBox.removeChild(cheatCodeBox.firstChild);
		}

    	switch (g_sceneinfo.cur_scene)
		{
			case gS_MAINMENU:
				// on_action_mainmenu (keyCode);

				// 치트키 데이터 배열
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					' a : 8성 캐릭터 획득',
					' b : 7성 캐릭터 획득',
					' c : 센언니/대천사 루시 7성 6개 캐릭터 획득',
					' e : 구름조각 11개 획득',
					' f : BP 50개 획득',
					' h : 루비 5천개, 골드 100만개 획득',
					' i : 아이템 B,C,D 획득',
					' l : 사용자 레벨 업',
					' m : 아군캐릭터 얻기',
					' n : 아이템 얻기',
					' o : 260 스테이지까지 OPEN',
					' p : 스마티 4성 7개',
					' s : 돈좀 줘',
					' q : 로컬에서 이미지 로딩 On/Off',
					' u : 업그레이드 및 타워각성 제거',
					' r : 영웅 선택권 획득',
				];
			break;
			case gS_SELECTSTAGE:
				var cheats = addCheatList_select_stage();
			break;
			case gS_PACKAGE_STORE:
			case gS_EVENT:

				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					' d :  결제 기록 지우기',
					' p :  결제 성공 ON/OFF',
					' q :  결제 한도 1억 상향',
				];

			break;
			case gS_CLOUD_GARDEN:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					'b :  아군 무적 ON',
					'c :  아군 무적 OFF',
					'g :  아군 타워 무적 상태 ON',
					'h :  아군 타워 무적 상태 OFF',
					' v :  게임승리',
				];

			break;
			case gS_DAYDUNGEON:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					'b :  아군 무적 ON',
					'c :  아군 무적 OFF',
					'd :  적군 무적 ON',
					'e :  적군 무적 OFF',
					'g :  아군 타워 무적 상태 ON',
					'h :  아군 타워 무적 상태 OFF',
					'j :  적군 타워 무적 상태 ON',
					'k :  적군 타워 무적 상태 OFF',
					'l :  적군 타워 미사일 발사 정지 ON',
					'm :  적군 타워 미사일 발사 정지 OFF',
					' v :  게임승리',
					' f : 게임 패배',
				];

			break;
			case gS_GAME:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					'하늘정원 a :  다음 웨이브',
					'b :  아군 무적 ON',
					'c :  아군 무적 OFF',
					'd :  적군 무적 ON',
					'e :  적군 무적 OFF',
					'g :  아군 타워 무적 상태 ON',
					'h :  아군 타워 무적 상태 OFF',
					'j :  적군 타워 무적 상태 ON',
					'k :  적군 타워 무적 상태 OFF',
					'l :  적군 타워 미사일 발사 정지 ON',
					'm :  적군 타워 미사일 발사 정지 OFF',
					'v :  게임승리',
					'f : 게임 패배',
					'z : PVP 무승부 (결투장, 클래식)',
					'PVP화면 6~0 : 적군 출전',
				];

			break;
			case gS_DAYDUNGEON_SELECT:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					' 1 : 요일별 진입 가능',
				];

			break;
			case gS_BOSS:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					'b :  아군 무적 ON',
					'c :  아군 무적 OFF',
					'g :  아군 타워 무적 상태 ON',
					'h :  아군 타워 무적 상태 OFF',
					' f : 게임 패배',
				];

			break;
			case gS_RANKING:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					' a :  도전할 웨이브?'
				];

			break;
			case gS_RANKING_PVP:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					'a : 자동으로 적군 출전',
					'b : 수동으로 적군 출전',
					'm : 거울 PVP ON',
					'n : 거울 PVP OFF'
				];

			break;
			case gS_RANKING_BOSS:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					'm : 월드보스 입장 ON',
					'n : 월드보스 입장 OFF'
				];

			break;
			case gS_SETTING:
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					' a : 아군도감캐릭터ALL적용',
					' b : 아군도감캐릭터 초기화',
					' c : 적군도감캐릭터 ALL 적용',
					' d : 적군도감캐릭터 ALL 미적용',
					' e : 게임 데이터를 초기화'
				];
			break;
			case gS_CHARBOOK_ENEMY: // 20240102_dblee 추가함
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					'숫자 : 적군 (81~90) AP와 HP 값 적용'
				];
			break;
			case gS_FOUR_GODS: // 20240102_dblee 추가함
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					' a : 사방신 게이지 139로 업데이트',
				];
			break;
			case gS_MODE_SELECT: // 20240102_dblee 추가함
				var cheats = [
				  	' ] : 창 닫기/열기',
				  	'키패드 1/F1 : 리모컨의 RED 키',
					'키패드 4/F4 : 리모컨의 BLUE 키',
					'` (숫자 1 왼쪽 키) : 리모컨의 BACK',
					' o : 하드모드 스테이지 오픈',
				];
			break;

		default:
			var cheats = ['이 화면에는 치트키가 없습니다',];
			break;

		}

		for (var i = 0; i < cheats.length; i++) {
			var p = document.createElement('p'); // 새 p 요소 생성
			p.textContent = cheats[i]; // 텍스트 콘텐츠 추가
			cheatCodeBox.appendChild(p); // cheatCodeBox div에 p 요소 추가
		}

    }


	/**
	 * keydown 이벤트를 등록하면 여기서도 이벤트가 온다.
	 * @return {[type]} [description]
	 */
	function initEventListener() {
		d = document;
		d.body.addEventListener("keydown", onKeydown.bind(this), true);

		menuEl = null;
        enableMenu = 0;

	}

	/**
	 * 타워 각성을 제거 한다.
	 * @param  {Function} callBack_fn callback function
	 */
	api.remove_tower_awakening = function(callBack_fn) {
		var server_url = SERVER_URL + 'Tower/remove_tower_awakening.php';
		var send_data = {};
		send_data.HOST_ID = glo.fun.get_uniq_id();

		var enable_crypt = 0;
		var options = {
			crypt: enable_crypt
			,url: server_url
			,send_data: send_data
			,success_fn: function(data)
			{
				var json_data = data;
				callBack_fn && callBack_fn(json_data);
				json_data = null;
			}
			,fail_fn:function(e)
			{
				glo.fun.show_s_error_network("서버 오류 - remove_tower_awakening");
			}
			,timeout_fn:null
		};
		PHPAjax.create().post_json_ajax(options);
	}




	// 20220420_dblee 테스트위해 ID와 국가 코드를 href에서 생성가능하도록 함.
	// SSVN를 테스트 위해서는 index.html?id=1111&country=VN 사용하면 된다.
	var is_enabled = false;
	var test_id = "";
	var test_country = "KR";
	/**
	 * [check_href_id description]
	 * @return {[type]} [description]
	 * @example bsdApp.app_test.get_is_enabled()
	 */
	api.get_is_enabled = function()
	{
		return is_enabled;
	}
	/**
	 * @example bsdApp.app_test.set_platform_ANDROID()
	 */
	api.set_platform_SKB = function()
	{
		if (!is_enabled) return false;
		gEntrix.user_phone = test_id;
		gEntrix.email = test_id;
		return true;
	}
	/**
	 * @example bsdApp.app_test.set_platform_ANDROID()
	 */
	api.set_platform_ANDROID = function()
	{
		if (!is_enabled) return false;
		gEntrix.email = test_id;
		gEntrix.user_address = test_id;
		return true;
	}
	/**
	 * @example bsdApp.app_test.set_platform_SS_SSBR()
	 */
	api.set_platform_SS_SSBR = function()
	{
		if (!is_enabled) return false;
		gEntrix.host_id = test_id;
		util_tizen.countryCode = test_country;
		return true;
	}
	/**
	 * @example bsdApp.app_test.set_platform_LGH_HCN_CNM()
	 */
	api.set_platform_LGH_HCN_CNM = function()
	{
		if (!is_enabled) return false;

		STORAGE.data1.id = test_id;
		glo.fun.set_uniq_id(test_id);
		return true;
	}
	/**
	 * @example bsdApp.app_test.set_platform_storage()
	 */
	api.set_platform_storage = function()
	{
		if (!is_enabled) return false;

		gEntrix.host_id = STORAGE.data1.id = test_id;
  		glo.fun.set_uniq_id(test_id);
		return true;
	}
	/**
	 * @example bsdApp.app_test.set_platform_LGH_HCN()
	 */
	api.set_platform_LGH_HCN = function()
	{
		if (!is_enabled) return false;
		gEntrix.host_id = test_id;
		gEntrix.SMART_CARD_ID = test_id;
		gEntrix.TERMINAL_CODE = test_id;
		return true;
	}
	/**
	 * @example bsdApp.app_test.set_platform_GLO()
	 */
	api.set_platform_GLO = function()
	{
		if (!is_enabled) return false;
		return test_id;
	}

	/**
	 * [check_href_id description]
	 * @return {[type]} [description]
	 * @example bsdApp.app_test.check_href_id()
	 */
	api.check_href_id = function()
	{
		if (gAPP_RELEASE === 'RELEASE') return;

		if (gTARGET_PLATFORM === gPLATFORM.ENTRIX_CJH || gTARGET_PLATFORM === gPLATFORM.HCN)
		{
			var parms = document.location.hash; // #version=3#siteCode=CJH#so=66#network=testbed#standalone#id=1111
			var tmp_1 = parms.split("#");
			for (var i in tmp_1)
			{
				if (typeof tmp_1[i] !== 'string') continue;
				var tmp = tmp_1[i].split("=");
				if (tmp[0].toLowerCase() == "id")
				{
					if(tmp[1] === "" || tmp[1] === null)
					{
						console.error("파라미터오류 입력형식: index.html#id=1111");
						return;
					}
					else
					{
						if(gTARGET_PLATFORM === gPLATFORM.ENTRIX_CJH) test_id = "TTED_LH_"+ tmp[1];
						else if(gTARGET_PLATFORM === gPLATFORM.HCN) test_id = "TTED_HC_"+ tmp[1];
						else test_id = "TTED_"+ tmp[1];
						is_enabled = true;
					}
				}
			}
		}
		else
		{
			var nowAddress	= location.href;
			var parameter	= nowAddress.slice(nowAddress.indexOf('?')+1,nowAddress.length); //id=1111
			if(nowAddress.indexOf('?') !== -1) //index.html에서 ?가 없다면
			{

				var tmp_1 = parameter.split("&");
				for (var i in tmp_1)
				{
					var tmp = tmp_1[i].split("=");
					if (tmp[0].toLowerCase() == "id")
					{
						if(tmp[1] === "" || tmp[1] === null)
						{
							console.error("파라미터오류 입력형식: index.html?id=1111");
							return;
						}
						else
						{
							if(gTARGET_PLATFORM === gPLATFORM.TIZEN_TV) test_id = "TTED_SS_"+ tmp[1];
							else if(gTARGET_PLATFORM === gPLATFORM.SSBR) test_id = "TTED_SSBR_"+ tmp[1];
							else if(gTARGET_PLATFORM === gPLATFORM.LGWEBOS_TV) test_id = "TTED_LG_"+ tmp[1];
							else if(gTARGET_PLATFORM === gPLATFORM.KT) test_id = "TTED_KT_"+ tmp[1];
							else if(gTARGET_PLATFORM === gPLATFORM.ENTRIX_CNM) test_id = "TTED_DL_"+ tmp[1];
							else if(gTARGET_PLATFORM === gPLATFORM.TOSS) test_id = "TTED_TOSS_"+ tmp[1];
							else if(glo.fun.is_glo_platform()) test_id = "TTED_GLO_"+ tmp[1];
							else if(glo.APP_FEATURE.ANDROID_BASE) test_id = tmp[1];
							else test_id = "TTED_"+ tmp[1];

							// 20230623_dblee BM ID로 테스트 하기 위해 예외처리함.
							if (glo.fun.is_glo_platform() && (tmp[1].indexOf('BM') !== -1 || tmp[1].indexOf('@') !== -1))
							{
								test_id = tmp[1];
							}
							else if (gTARGET_PLATFORM === gPLATFORM.LGWEBOS_TV && (tmp[1].indexOf('ElDorado') !== -1))
							{ // 20250826_dblee 실제 사용자 ID로 테스트 할 수 있도록 함.
								test_id = tmp[1];
							}

							is_enabled = true;
						}
					}
					else if (tmp[0].toLowerCase() == "userid")
					{
						// 20220512_dblee 실제 사용자 ID를 넣어서 사용할때
						test_id = tmp[1];
						is_enabled = true;
					}
					else if (tmp[0].toLowerCase() === "country")
					{
						test_country = tmp[1];
						if (test_country !== "EN" && test_country !== "VN") test_country = "KR";
						// TIZEN_TV는 SS,SSVN 나눈다.
						if (gTARGET_PLATFORM === gPLATFORM.TIZEN_TV && tmp[1].toLowerCase() === "vn")
						{
							glo.TEST_MODE.ENALBE_VN_COUNTRY = 1;
							test_id = test_id.replace("SS", "SSVN");
						}
					}
				}
			}
		}
	}



	/**
	 * 해당 HOST_ID를 IceHunter__PingbackDB 테이블에서 지운다.
	 * @example delete_pingback()
	 */
	function delete_pingback() {
		var server_url = SERVER_URL + 'pingback/delete_pingback.php';
		var send_data = {};
		send_data.HOST_ID = glo.fun.get_uniq_id();

		var enable_crypt = 0;
		var options = {
			crypt: enable_crypt
			,url: server_url
			,send_data: send_data
			,success_fn: function(data)
			{
				if (typeof data === 'string' && data === 'OK')
					utilNotice("완료 - delete_pingback", 2);
				else
					utilNotice("제한 오류 - delete_pingback", 2);
			}
			,fail_fn:function(e)
			{
				utilNotice("서버 오류 - delete_pingback", 2);
			}
			,timeout_fn:null
		};
		PHPAjax.create().post_json_ajax(options);
	}

	api.init();

	return api;

})();


