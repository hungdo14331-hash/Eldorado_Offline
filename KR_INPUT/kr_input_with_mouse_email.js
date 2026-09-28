/********************************************************************
 * KR_INPUT
 *
 * 2017.09.24 busidol.ywlee
 * 2017.10.07 1차 버전 완성
 * 2019.05.23 한영전환 및 대소문자 추가
 * 2020.02.28 마우스 될수 있게 구현하기 ywlee
 *
 * TV리모컨으로 한글 입력에 있어 불편함이 있고 또한
 * CJH, DLIVE등의 입력 방식이 달라 독자 방식으로 가기고 결정 함.
 * TV리모컨은 키보드가 아니고 모바일이 아니다.
 * 키보드는 사람들이 손가락이 기억해서 치는 것이다.
 * TV리모컨으로는 키보드 배열이 맞지 않다. 눈으로 인지해야 하기 때문이다.
 * 그렇다고 모바일 처럼 빠르게 칠수 있는 것도 아니기에 천지인 보다는
 * 자음/모음의 배치만으로 해결 하는 것이 좋아 보인다. -busidol.ywlee-
 *
 ********************************************************************/

var KR_INPUT =
{
    CallBackFn : null, // 입력완료 눌렀을때 호출 되는 함수 KR_INPUT.init()의 인자로 날라옴.
    before_str : null, // 기존에 입력 되었던 값.KR_INPUT.init()의 인자로 날라옴.


    MAX_CHAR : 5, //최고 입력 길이
    MIN_CHAR : 2, //최소 입력 길이

    //입력을 위한 키보드 자판 배열
    div    : null,
    row1   : ["",  "1",    "2",    "3",    "4",    "5",    "6",    "7",    "8",    "9",  "0"],
    row2   : ["",  "ㄱ",     "ㄴ",   "ㄷ",   "ㄹ",   "ㅁ",   "ㅏ",   "ㅑ",   "ㅓ",   "ㅕ",   "←"],
    row3   : ["",  "ㅂ",     "ㅅ",   "ㅇ",   "ㅈ",   "ㅊ",   "ㅗ",   "ㅛ",   "ㅜ",   "ㅠ"],
    row4   : ["",  "ENG",    "ㅋ",   "ㅌ",   "ㅍ",   "ㅎ",   "ㅡ",   "ㅣ",   "",     "",     ""],
  //row5   : ["",  "",       "",   "",   "",   "",    "",     "",     "",     "",     ""],
    row5   : ["",  "SPACE"],
    row_focus : 1, //1행
    col_focus : 1, //1열

    string : null, //사용자 입력 string
    tmp_str : [],   //1부터 MAX_CHAR까지의배열이다.
    tmp_focus : 0,  //0부터 MAX_CHAR까지의 값을 가진다. tmp_str에 아무것도 없으면0, 1번자리에 뭔가 들어가면 1, 2번자리에 뭔가 들어가면 2 이다.

    blink_timer : null,

    parentEl : null,    // IME 연결할 부모 Element  20171026.dblee
    KEY :               // 외부에서 KEY 값을 이용할 수 있도록 함. 20171026.dblee
    {
        LEFT    : 'LEFT',
        RIGHT   : 'RIGHT',
        UP      : 'UP',
        DOWN    : 'DOWN',
        ENTER   : 'ENTER',
        ESC     : 'ESC',
        BACK    : 'BACK',
        ERASE    : 'ERASE',    // SKB 용 지우기 버튼. 20190418.dblee
    },

    mode_kor_eng    : "KOR",   //"KOR","ENG"
    mode_aA         : "A",            //"A" 대문자, "a" 소문자
    mother_lang     : "KOR",    //팝업 호출되기전의 언어값

    title   : "변경할 이름을 입력하세요!",
    caution : "주의! 부적절한 이름(욕설 등)을 사용할 경우 사전 공지없이 계정 정지 됨.",

    //유니코드 계산을 위한 배열 -- 이 배열은 0 번지 부터 사용함.^^
    cho  : ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'], //초성은 19개
    jung : ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ'], //중성은 21개
    jong : [ ' ','ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'], //종성은 28개 .. 종성의 0번째는 공백

    use_special_char : true,
    check_str : true,
    has_init_btn : false, //초기화 버튼 사용 여부
    email_check: false // email 형식인지 체크를 한다. // 20260309_dblee 사용자 키 기능 구현(202603091450)
}

/**
 * KeyDefine이 다른 곳에서 선언 되어 있으면 그 값을 가져오고 그렇지 않으면 선언 한다. 20171026.dblee
 * @type {Object}
 */
var KeyDefine = KeyDefine = KeyDefine || {
    left    : 37,
    right   : 39,
    up      : 38,
    down    : 40,
    enter   : 13,
    esc     : 27,
    back    : 8,
};

//IME를 보이고 싶은 타이밍에 이 함수만 호출하면 자동으로 된다.
//CallBackFn : 입력완료받고 호출해야 할 함수
//str : 미리 입력된 값이있다면 받아온다.
//len : 입력받을 text길이( 정의되지 않으면 default값 MAX_CHAR(5)로 설정된다.
//parentEl : IME 연결할 부모 Element. -- 이돈복부장님 스타일 사용시(시나리오(화면)하나 만들어 연결할때)
KR_INPUT.init = function(CallBackFn, str, len, parentEl, obj, len_min)
{
    if(typeof CallBackFn !== "function")
    {
        console.log("CallBackFn("+CallBackFn+")은 정상 함수가 아니다.");
        //  alert("KR_INPUT.init(CallBackFn)에서 CallBackFn에 대해 정의 한후 호출 바랍니다.");
        return;
    }

    // IME 연결할 부모 Element을 등록한다. 20171026.dblee
    if(typeof parentEl != 'undefined' ) {
        KR_INPUT.parentEl = parentEl;
        parentEl = null;
    }

    //MAX_CHAR의 설정 : 최고 len 길이 까지 입력 받아 들인다.
    KR_INPUT.before_str = str;
    KR_INPUT.CallBackFn = CallBackFn;
    if(len != null && len != '')
        KR_INPUT.MAX_CHAR = len;
    else
        KR_INPUT.MAX_CHAR = 5;

    if(len_min != null && len_min != '')
        KR_INPUT.MIN_CHAR = len_min;
    else
        KR_INPUT.MIN_CHAR = 2;



    //obj에 관해
    if (obj == null)
    {   
        //default
        obj = 
        {
            lang    :"KOR",
            title   :"변경할 이름을 입력하세요!",
            // 20260309_dblee 사용자 키 기능 구현(202603091450)
            mode_aA : 'A', // 20260312_dblee 영어의 대/소문자 구별
            email_check : false, // 20260312_dblee 이메일 형식인지 체크를 한다.
            caution :"주의! 부적절한 이름(욕설 등)을 사용할 경우 사전 공지없이 계정 정지 됨.",

        };
    }

    // 20260309_dblee 사용자 키 기능 구현(202603091450)
    // 20260312_dblee 영어의 대/소문자 구별. 이메일 형식인지 체크를 한다.
    KR_INPUT.mode_aA = (obj.mode_aA == 'a') ? 'a' : 'A';
    KR_INPUT.email_check = (obj.email_check == true) ? true : false;

    //기본언어 설정
    KR_INPUT.mode_kor_eng = KR_INPUT.mother_lang = obj.lang; //"KOR","ENG"    
    KR_INPUT.row_change(); //KOR,ENG값을 설정했으면 row2,3,4를 설정한다.

    //title 및 caution설정
    KR_INPUT.title      = obj.title;
    KR_INPUT.caution    = obj.caution == null ? "" : obj.caution;
    
    KR_INPUT.string = "";   //입력값 우선 초기화

    //글자 조합을 위해 필요한 tmp_str을 생성한다. 아래 벼열에 대한 설명은 "자판배열.xls"두번째탭을 참고 바람.
    for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
    {
        KR_INPUT.tmp_str[i]          = {};
        KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
        KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
        KR_INPUT.tmp_str[i].cho      = null; //초성
        KR_INPUT.tmp_str[i].jung     = null; //중성
        KR_INPUT.tmp_str[i].jong     = null; //종성
    }

    KR_INPUT.tmp_focus = 0;
    KR_INPUT.row_focus = 1;
    KR_INPUT.col_focus = 1;

    if(str != null && str != '') //기본 입력된 data가 있다면 backspace에 focus를 가져가게 하라.
    {
        KR_INPUT.row_focus = 2;
        KR_INPUT.col_focus = 10;
    }

    KR_INPUT.blink_timer = null;

    KR_INPUT.make_tag();
    KR_INPUT.make_screen();
    KR_INPUT.draw_focus(1,1); //

    if (KR_INPUT.parentEl == null) {
        //key event를 등록 한다.
        document.body.onkeydown = KR_INPUT.key_event;
        //document.addEventListener("keydown",KR_INPUT.key_event,false);
    }
    //KR_INPUT.notice("테스트 입니다.");

    //str에 기본 값이 왔다면 그 기본값을 화면에 보여줘라.
    if(str != null && str !='')
    {
        var len = str.length;
        if(len > KR_INPUT.MAX_CHAR) len = KR_INPUT.MAX_CHAR;
        for(var i=0;i<len;i++)
        {
            KR_INPUT.tmp_str[i+1].status = "CK"; //완료된 한글로 우선 간주해 버리자
            KR_INPUT.tmp_str[i+1].complete = str.charAt(i);
        }
        KR_INPUT.tmp_focus = len;
        KR_INPUT.string_make();
        KR_INPUT.draw_string();
    }

    // 20260309_dblee 사용자 키 기능 구현(202603091450) - 마우스도 작동되게 함
    //20200228_ywlee 마우스도 작동되게 하자
    var mou = document.getElementsByClassName("button");
    for(var i=0;i<mou.length;i++)
    {    
        // mou[i].addEventListener('click',KR_INPUT.mouse_click);    // 중복 입력되어 주석처리 함
        mou[i].addEventListener('mouseover',KR_INPUT.mouse_over); 
    }

    KR_INPUT.set_has_init_btn(false);
    KR_INPUT.set_check_str(true);
    KR_INPUT.set_special_char(true);

    KR_INPUT.fitToViewport();

    setTimeout(function() { gEnableKey = 1; }, DEFINE.KEYLOCKTIME); // 화면 다 그리고 500미리 세컨드 후에 key 입력 받기.

}

KR_INPUT.removeMouseEvent = function()
{
	if(!gMOUSE_USE) return; //cnm의 경우 마우스 기능을 제거 한다. // 마우스변수 추가함.  3.25.2016
	$("#KR_INPUT_div").unbind('mouseover');
};

KR_INPUT.keyDown = function(event, key)
{
	var keyCode = (key==null)?event.keyCode : key;
	
    KR_INPUT.key_event(keyCode);

}

// 20240412_dblee_1341 마우스 오버 및 드래그 기능 구현
KR_INPUT.onClick = function(e)
{
	if(!gMOUSE_USE) return;

	//연속 클릭 방지 20170110_ywlee
	if(gEnableKey == 0) return;

	utilConsoleLog(" KR_INPUT.onClick  e.target.id: "+e.target.id+"   currentTarget:"+e.currentTarget.id);

	// 20231215_dblee 포커스된 버튼/메뉴에서 화면 배경에 클릭하면 실현되는 현상 수정함.
	var elm = e.target;
	while(!(elm.className && elm.className.search('button') >= 0)) {
		elm = elm.parentNode;
		if(elm == null || elm.nodeName == 'BODY' || elm.nodeName == 'HTML') {
			elm = null;
			return;
		}
	}

    KR_INPUT.mouse_click(e);

};

// 20240412_dblee_1341 마우스 오버 및 드래그 기능 구현
KR_INPUT.onMouseover = function(e)
{
	if(!gMOUSE_USE) return;
	if(gEnableKey == 0) return;

	var elm = e.target;
	while(!(elm.className && elm.className.search('button') >= 0)) {
		elm = elm.parentNode;
		if(elm == null || elm.nodeName == 'BODY' || elm.nodeName == 'HTML') {
			elm = null;
			return;
		}
	}

    KR_INPUT.mouse_over(e);

};

KR_INPUT.onMousedown = function(e)
{
	utilConsoleLog(" KR_INPUT.onMousedown  e.target.id: "+e.target.id+"   currentTarget:"+e.currentTarget.id);
	KR_INPUT.onMouseover(e);
	return;
}
// 20240412_dblee_1341 마우스 오버 및 드래그 기능 구현
KR_INPUT.onMouseup = function(e)
{
	utilConsoleLog(" KR_INPUT.onMouseup  e.target.id: "+e.target.id+"   currentTarget:"+e.currentTarget.id);
	KR_INPUT.onMouseover(e);
	KR_INPUT.onClick(e);
	return;
}

//20200228_ywlee 마우스도 작동되게 하자
KR_INPUT.mouse_click = function(e)
{
    console.log("mouse click!:"+e.target.id);

    if(['MCA_board_id', 'MCA_board_id_value', 'MCA_board_pw', 'MCA_board_pw_value'].includes(e.target.id))
    {
        return;
    }

    //강제로 key event의 enter를 발생 시킨다.
    var e = {
                keyCode:KR_INPUT.KEY.ENTER,
                preventDefault : function(){},
                stopPropagation : function(){}
            };
    KR_INPUT.key_event(e);

}

KR_INPUT.mouse_over = function(e)
{
    console.log("mouse over!:"+e.target.id);

    //눌러진곳이 몇행 몇열 인지 파악하자.
    var before_row = KR_INPUT.row_focus;
    var before_col = KR_INPUT.col_focus;

    //1.혹시 제일 아래 버턴인 OK,CANCEL눌렀나 체크하기.
    switch(e.target.id)
    {
        case "KIdiv_btn_1": //확인
                            KR_INPUT.row_focus = 6; KR_INPUT.col_focus = 1; KR_INPUT.draw_focus(before_row,before_col);break;
        case "KIdiv_btn_2": //취소
                            KR_INPUT.row_focus = 6; KR_INPUT.col_focus = 2; KR_INPUT.draw_focus(before_row,before_col);break;
        case "KIdiv_btn_3": //초기화
                            KR_INPUT.row_focus = 6; KR_INPUT.col_focus = 3; KR_INPUT.draw_focus(before_row,before_col);break;

        default: //나누자."KIdiv_row4_10"
                var dummy = e.target.id.substr(9,4).split("_"); // 4_10 을 추출해 낸다.긜고, 4,10을 추출한다.
                if(dummy.length != 2) //2개의 좌표가 나오지 않는다면 그것도 오류이다.
                {
                    console.log("Error! undefind e.target.id:"+e.target.id);
                    return;
                }
                var row = parseInt(dummy[0],10);
                var col = parseInt(dummy[1],10);

                if(row == 0 || col == 0) //col,row는 1부터 시작하는데 0값이 나온다면 이것도 문제이다.
                {
                    console.log("Error! col ="+col+"   row="+row);
                    return;
                }
                //정상적인 row,col 값이라면 focus이동하자.
                KR_INPUT.row_focus = row; 
                KR_INPUT.col_focus = col; 
                KR_INPUT.draw_focus(before_row,before_col);
                break;
    }
}

//입력기가 화면에서 사라질 필요가 있을때 호출 된다.
KR_INPUT.end = function()
{
    // 초기화 함 20171026.dblee
    clearInterval(KR_INPUT.blink_timer); KR_INPUT.blink_timer = null;
    
    var parent = KR_INPUT_div.parentElement;
    parent.removeChild(KR_INPUT_div);

    if (KR_INPUT.parentEl == null) {
        //keyevent를 죽인다.
        document.body.onkeydown = null;
        //document.removeEventListener("keydown",KR_INPUT.key_event);
    }
    KR_INPUT.parentEl = null;

    //20200228_ywlee 마우스도 작동되게 하자
    var mou = document.getElementsByClassName("button");
    for(var i=0;i<mou.length;i++)
    {    
        mou[i].removeEventListener('click',KR_INPUT.mouse_click); 
        mou[i].removeEventListener('mouseover',KR_INPUT.mouse_over); 
    }
}

//한글 입력기의 tag들을 구성한다.
KR_INPUT.make_tag = function()
{
    //body의 제일 끝부분에 생성해야 한다.
    // KR_INPUT_div 가 있으면 지우고 새롭게 만든다. 20171026.dblee
    var KR_INPUT_div = document.getElementById("KR_INPUT_div");
    if (KR_INPUT_div != null) {
        var parent = KR_INPUT_div.parentElement;
        parent.removeChild(KR_INPUT_div);
    }
    KR_INPUT_div = document.createElement('DIV');
    KR_INPUT_div.setAttribute('id', "KR_INPUT_div");
    var KI_bg = document.createElement('DIV');
    KI_bg.setAttribute('id', "KI_bg");
    var KR_INPUT_widow_div = document.createElement('DIV');
    KR_INPUT_widow_div.setAttribute('id', "KR_INPUT_widow_div");

    KR_INPUT_div.appendChild(KI_bg);
    KR_INPUT_div.appendChild(KR_INPUT_widow_div);

    var container = KR_INPUT.parentEl
        || document.getElementById('div_body')
        || document.body; // 폴백

    container.appendChild(KR_INPUT_div);

    KR_INPUT.div = document.getElementById("KR_INPUT_widow_div");
    KR_INPUT.div.innerHTML =
        '<div id="KIdiv_input_name"></div>'+ //변경할 닉네임을 입력하세요
        '<div id="KIdiv_input_window"></div>'+

        '<div id="KIdiv_row1_1" class="button"></div>'+  //숫자0
        '<div id="KIdiv_row1_2" class="button"></div>'+  //숫자1
        '<div id="KIdiv_row1_3" class="button"></div>'+  //숫자2
        '<div id="KIdiv_row1_4" class="button"></div>'+  //숫자3
        '<div id="KIdiv_row1_5" class="button"></div>'+  //숫자4
        '<div id="KIdiv_row1_6" class="button"></div>'+  //숫자5
        '<div id="KIdiv_row1_7" class="button"></div>'+  //숫자6
        '<div id="KIdiv_row1_8" class="button"></div>'+  //숫자7
        '<div id="KIdiv_row1_9" class="button"></div>'+  //숫자8
        '<div id="KIdiv_row1_10" class="button"></div>'+ //숫자9

        '<div id="KIdiv_row2_1" class="button"></div>'+ //ㄱ
        '<div id="KIdiv_row2_2" class="button"></div>'+ //ㄴ
        '<div id="KIdiv_row2_3" class="button"></div>'+ //ㄷ
        '<div id="KIdiv_row2_4" class="button"></div>'+ //ㄹ
        '<div id="KIdiv_row2_5" class="button"></div>'+ //ㅁ
        '<div id="KIdiv_row2_6" class="button"></div>'+ //ㅏ
        '<div id="KIdiv_row2_7" class="button"></div>'+ //ㅑ
        '<div id="KIdiv_row2_8" class="button"></div>'+ //ㅓ
        '<div id="KIdiv_row2_9" class="button"></div>'+ //ㅕ
        '<div id="KIdiv_row2_10" class="button"></div>'+ //삭제

        '<div id="KIdiv_row3_1" class="button"></div>'+  //ㅂ
        '<div id="KIdiv_row3_2" class="button"></div>'+  //ㅅ
        '<div id="KIdiv_row3_3" class="button"></div>'+  //ㅇ
        '<div id="KIdiv_row3_4" class="button"></div>'+  //ㅈ
        '<div id="KIdiv_row3_5" class="button"></div>'+  //ㅊ
        '<div id="KIdiv_row3_6" class="button"></div>'+  //ㅗ
        '<div id="KIdiv_row3_7" class="button"></div>'+  //ㅛ
        '<div id="KIdiv_row3_8" class="button"></div>'+  //ㅜ
        '<div id="KIdiv_row3_9" class="button"></div>'+  //ㅠ
//        '<div id="KIdiv_row3_10" ></div>'+ //삭제

        '<div id="KIdiv_row4_1" class="button"></div>'+  //공백
        '<div id="KIdiv_row4_2" class="button"></div>'+  //ㅋ
        '<div id="KIdiv_row4_3" class="button"></div>'+  //ㅌ
        '<div id="KIdiv_row4_4" class="button"></div>'+  //ㅍ
        '<div id="KIdiv_row4_5" class="button"></div>'+  //ㅎ
        '<div id="KIdiv_row4_6" class="button"></div>'+  //ㅡ
        '<div id="KIdiv_row4_7" class="button"></div>'+  //ㅣ
        '<div id="KIdiv_row4_8" class="button"></div>'+  //공백
        '<div id="KIdiv_row4_9" class="button"></div>'+  //공백
        '<div id="KIdiv_row4_10" class="button"></div>'+ //공백
/*
        '<div id="KIdiv_row5_1" ></div>'+  //공백
        '<div id="KIdiv_row5_2" ></div>'+  //공백
        '<div id="KIdiv_row5_3" ></div>'+  //공백
        '<div id="KIdiv_row5_4" ></div>'+  //ㅍ
        '<div id="KIdiv_row5_5" ></div>'+  //ㅎ
        '<div id="KIdiv_row5_6" ></div>'+  //공백
        '<div id="KIdiv_row5_7" ></div>'+  //공백
        '<div id="KIdiv_row5_8" ></div>'+  //공백
        '<div id="KIdiv_row5_9" ></div>'+  //공백
        '<div id="KIdiv_row5_10" ></div>'+ //공백
*/
        '<div id="KIdiv_row5_1" class="button"></div>'+ //space

        '<div id="KIdiv_btn_1" class="button"></div>'+ //확인
        '<div id="KIdiv_btn_2" class="button"></div>'+ //취소
        '<div id="KIdiv_btn_3" class="button"></div>'+ //초기화

        '<div id="KIdiv_msg"></div>'+    //메시지 --첫문자는 공백으로 사용 할 수 없습니다.

        '<div id="KIdiv_caution"></div>'+  //경고문구!
        '';
}
/**
 * 이 함수에서 사용하는 것만 적용됨.
 * '#KR_INPUT_div' 만 되고 하나의 tag만 가능함.
 * @param  {String} cssElId css 타입의 태그 아이디 ex. '#KR_INPUT_div'
 * @param  {Obejct} cssObj  css 정보 값
 */
KR_INPUT.make_css = function(cssElId, cssObj)
{

    // console.log( "make_css cssElId :" +cssElId);
    var el;
    if (typeof cssElId  ==  'string' || typeof cssElId  ==  'String') {
        el = document.querySelector(cssElId);
    } else if (typeof cssElId != 'undefined' && (typeof cssElId == 'object' || typeof cssElId == 'Object')) {
        el = cssElId;
    }
    
    if (el == null)
    {
        return null;
    }

    // console.log( "make_css cssElId instanceof Element :" +(cssElId instanceof Element));
    for (var s in cssObj) {
        //console.log( "make_css cssElId instanceof s :" +s);
        switch (s)
        {
            case 'transform' :
                el.style['transform'] = cssObj[s];
                el.style['WebkitTransform'] = cssObj[s];
            break;
            case 'transform-origin' :
                el.style['transformOrigin'] = cssObj[s];
                el.style['WebkitTransformOrigin'] = cssObj[s];
            break;
            case 'line-height' :
                el.style['lineHeight'] = cssObj[s];
            break;
             case 'font-size' :
                el.style['fontSize'] = cssObj[s];
            break;
            case 'text-align' :
                el.style['textAlign'] = cssObj[s];
            break;
             case 'text-shadow' :
                el.style['textShadow'] = cssObj[s];
            break;
             case 'border-radius' :
                el.style['borderRadius'] = cssObj[s];
                el.style['WebkitBorderRadius'] = cssObj[s];
            break;
             case 'box-shadow' :
                el.style['boxShadow'] = cssObj[s];
                el.style['WebkitBoxShadow'] = cssObj[s];
            break;
              case 'font-family' :
                el.style['fontFamily'] = cssObj[s];
            break;
            default:
                el.style[s] = cssObj[s];
            break;

        }

    }
    return el;
}

//keyboard화면을 그린다.
KR_INPUT.make_screen = function()
{
    util_draw_div('KR_INPUT_div', 0, 0, 1280, 720);

    var bw = 76;    //btn width
    var bh = 60;    //btn height
    var bgap = 12;   //btn gap
    var left_m = 206 //btn left margine 시작시
    var btn_top = 205;

    var KR_INPUT_div = document.getElementById("KR_INPUT_div");
    //배경 -- opacity 처리
    // 컨테이너: 화면 전체 고정
    KR_INPUT.make_css('#KR_INPUT_div', {
        position: 'fixed',
        left: '0px',
        top: '0px',
        width: '100vw',
        height: '100vh',
        zIndex: 2147483000   // 최상단(원하면 낮춰도 됨)
    });

    // 검은 배경: 화면 전체 덮기
    KR_INPUT.make_css('#KI_bg', {
        position: 'fixed',
        left: '0px',
        top: '0px',
        width: '100%',
        height: '100%',
        background: 'rgba(0,0,0,0.85)'  // 불투명도 조절
        // opacity는 rgba로 대체했으므로 생략
    });

    // 키보드 본체는 기준 해상도 유지(여기에만 스케일 적용할 것)
    KR_INPUT.make_css('#KR_INPUT_widow_div', {
        position: 'absolute',
        left: '0px',
        top: '0px',
        width: '1280px',
        height: '720px'
    });

    //타이틀
    KR_INPUT.make_css('#KIdiv_input_name', {
        left            : 206+'px',
        top             : 60+'px',
        width           : 868+'px',
        height          : 44+'px',
        //background      : 'none',
        'line-height'   : '44px',
        'font-size'     : '33px',
        'color'         : '#ffffff',
        'text-align'    : 'center',
       // 'text-shadow'   : '1px 1px 1px black',
        position    : 'absolute'
    }).innerHTML = KR_INPUT.title;//"변경할 이름을 입력하세요!";

    //input창
    KR_INPUT.make_css('#KIdiv_input_window', {
        left        : '382px',
        top         : '109px',
        width       : '516px',
        height      : '55px',
        background  : '#ffffff',
        position    : 'absolute'
    });
    KR_INPUT.draw_string();//아무것도 없겠지만 우선 string값을 표기 하라.

    //첫번째 줄 그리기
    for(var i=1;i<KR_INPUT.row1.length;i++)
    {
        KR_INPUT.make_css('#KIdiv_row1_'+i, {
            left            : left_m + bw *(i-1)+ bgap*(i-1)+'px',
            top             : btn_top +'px',
            width           : bw+'px',
            height          : bh+'px',
            background      : KR_INPUT.get_bg(KR_INPUT.row1[i]),
            'line-height'   : '60px',
            'font-size'     : '35px',
            'color'         : '#ffffff',
            'text-align'    : 'center',
            'border-radius' : '5px',
            'opacity'       : 0.85,
            'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
            position    : 'absolute'
        }).innerHTML = KR_INPUT.row1[i];

        //back space의 경우 더 넓다.
//        if (i == 13)
//            $('#KIdiv_row1_'+i).css({width           : bw*2+bgap+'px'});
    }

    //두번째 줄 그리기
    for(var i=1;i<KR_INPUT.row2.length-1;i++)
    {
        KR_INPUT.make_css('#KIdiv_row2_'+i, {
            left            : left_m + bw *(i-1)+ bgap*(i-1)+'px',
            top             : btn_top + bh + bgap +'px',
            width           : bw+'px',
            height          : bh+'px',
            background      : KR_INPUT.get_bg(KR_INPUT.row2[i]),//'gray',
            'line-height'   : '60px',
            'font-size'     : '35px',
            'color'         : '#ffffff',
            'text-align'    : 'center',
            'border-radius' : '5px',
            'opacity'       : 0.85,
            'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
            position    : 'absolute'
        }).innerHTML = KR_INPUT.row2[i];
    }
    //back space는 크게
    KR_INPUT.make_css('#KIdiv_row2_'+10, {
        left            : left_m + bw *(10-1)+ bgap*(10-1)+'px',
        top             : btn_top + bh + bgap +'px',
        width           : bw+'px',
        height          : 132+'px',
        background      : KR_INPUT.get_bg(KR_INPUT.row2[10]),//'gray',
        'line-height'   : '132px',
        'font-size'     : '35px',
        'color'         : '#ffffff',
        'text-align'    : 'center',
        'border-radius' : '5px',
        'opacity'       : 0.85,
        'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
        position    : 'absolute'
    }).innerHTML = KR_INPUT.row2[10];


    //세번째 줄 그리기
    for(var i=1;i<KR_INPUT.row3.length;i++)
    {
        KR_INPUT.make_css('#KIdiv_row3_'+i, {
            left            : left_m + bw *(i-1)+ bgap*(i-1)+'px',
            top             : btn_top + (bh + bgap)*2 +'px',
            width           : bw+'px',
            height          : bh+'px',
            background      : KR_INPUT.get_bg(KR_INPUT.row3[i]),
            'line-height'   : '60px',
            'font-size'     : '35px',
            'color'         : '#ffffff',
            'text-align'    : 'center',
            'border-radius' : '5px',
            'opacity'       : 0.85,
            'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
            position    : 'absolute'
        }).innerHTML = KR_INPUT.row3[i];
    }

    //네번째 줄 그리기
    for(var i=1;i<KR_INPUT.row4.length;i++)
    {
        var font_size = 35; 
        var line_height = 60;

        //if(KR_INPUT.row4[i] == "KOR" || KR_INPUT.row4[i] == "ENG")
        if(KR_INPUT.row4[i] == "KOR" || KR_INPUT.row4[i] == "ENG" || KR_INPUT.row4[i] == "#+=")
        {
            font_size = 25;
        }

        if(KR_INPUT.row4[i] == "Upper case" || KR_INPUT.row4[i] == "Lower case")
        {
            font_size = 22;
            line_height = 30;
        }

        KR_INPUT.make_css('#KIdiv_row4_'+i, {
            left            : left_m + bw *(i-1)+ bgap*(i-1)+'px',
            top             : btn_top + (bh + bgap)*3 +'px',
            width           : bw+'px',
            height          : bh+'px',
            background      : KR_INPUT.get_bg(KR_INPUT.row4[i]),
            'line-height'   : line_height+'px',
            'font-size'     : font_size+'px',
            'color'         : '#ffffff',
            'text-align'    : 'center',
            'border-radius' : '5px',
            'opacity'       : 0.85,
            'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
            position    : 'absolute'
        }).innerHTML = KR_INPUT.row4[i];
    }

    //다섯번째 줄 그리기 스페이스바
    KR_INPUT.make_css('#KIdiv_row5_1', {
        left            : 206 + 'px', //294
        top             : 493 +'px',
        width           : 692 + 176 +'px', //692
        height          : 60 +'px',
        background      : KR_INPUT.get_bg(KR_INPUT.row5[i]),
        'line-height'   : '60px',
        'font-size'     : '35px',
        'color'         : '#ffffff',
        'text-align'    : 'center',
        'border-radius' : '5px',
        'opacity'       : 0.85,
        'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
        position    : 'absolute'
    }).innerHTML = "SPACE";


    //버턴2개 (확인,취소)
    KR_INPUT.make_css('#KIdiv_btn_1', {
        left            : '470px',
        top             : '594px',
        width           : '164px',
        height          : '60px',
        background      : '#596b77',
        'line-height'   : '60px',
        'font-size'     : '35px',
        'color'         : '#ffffff',
        'text-align'    : 'center',
        'border-radius' : '5px',
        'opacity'       : 0.85,
        'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
        position    : 'absolute'
    }).innerHTML = (KR_INPUT.mother_lang == "KOR")? "확인" : "OK";

    KR_INPUT.make_css('#KIdiv_btn_2', {
        left            : '646px',
        top             : '594px',
        width           : '164px',
        height          : '60px',
        background      : '#596b77',
        'line-height'   : '60px',
        'font-size'     : '35px',
        'color'         : '#ffffff',
        'text-align'    : 'center',
        'border-radius' : '5px',
        'opacity'       : 0.85,
        'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
        position    : 'absolute'
    }).innerHTML =  (KR_INPUT.mother_lang == "KOR")? "취소":"Cancel";

    KR_INPUT.make_css('#KIdiv_caution', {
        left            : '0px',
        top             : 493+65+'px',
        width           : 1280+'px',
        height          : '60px',
        //background      : '#596b77',
        'line-height'   : '35px',
        'font-size'     : '22px',
        'color'         : 'yellow',
        'text-align'    : 'center',
        //'border-radius' : '5px',
        //'opacity'       : 0.85,
        //'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
        position    : 'absolute'
    }).innerHTML = KR_INPUT.caution;//"주의! 부적절한 이름(욕설등)을 사용할 경우 계정 정지 됨을 알려 드립니다.";

}

//버턴배경색상을 string 형태로 return한다.
KR_INPUT.get_bg = function(ch)
{
    //어떤문자인지 받아온다.
    //var ch = eval("KR_INPUT.row"+row+"[col]");

    //빈공백
    if(ch == '') return "#0e1013";

    //자음버턴
    var jaeum="ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ";
    if(jaeum.indexOf(ch) != -1) return "#54819f";

    //모음버턴
    var moeum="ㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣ";
    if(moeum.indexOf(ch) != -1) return "#859eae";

    
    //KOR/ENG버턴   
    if(ch == "KOR" || ch == "ENG" || ch == "#+=") return "#ca3333";

    //대소문자 버턴
    if(ch == "Lower case" || ch == "Upper case") return "#ca3333";
    
    
    //기본색상
    return "#596b77";

}

//메시지 창
//첫문자는공백을 사용할 수 없습니다. 등등
KR_INPUT.notice = function(str)
{
    KR_INPUT.make_css('#KIdiv_msg', {
        display         : 'block',
        left            : 174 +'px',
        top             : 319 +'px',
        width           : 932 +'px',
        height          : 48+'px',
        background      : '#fff0b4',
        'line-height'   : '48px',
        'font-size'     : '25px',
        'color'         : '#a70000',
        'text-align'    : 'center',
        'border-radius' : '5px',
        'border'        : '1px solid #3f4d4c',
        //'text-shadow'   : '1px 1px 1px black',
        position    : 'absolute'
    }).innerHTML = str;

    setTimeout(function()
    {
        var msgEl = KR_INPUT.make_css('#KIdiv_msg', {display:'none'});
        if (msgEl)
        {
            msgEl.innerHTML = "";
        }
        
    },1500);

}
//키 이벤트의 등록
KR_INPUT.key_event = function(e)
{
    // KR_INPUT.parentEl 값에 따라서 keyCode 값을 다르게 대입 함. 20171026.dblee
    var keyCode;

    if(typeof e == 'number' || KR_INPUT.parentEl != null)
        keyCode = e;
    else 
        keyCode = e.keyCode;

    console.log("key="+keyCode);
    var before_row = KR_INPUT.row_focus;
    var before_col = KR_INPUT.col_focus;

    switch(keyCode)
    {
        case KR_INPUT.KEY.ERASE: // 20190118.dblee
                if(KR_INPUT.tmp_focus <= 0) {console.log("empty");return;}

                //한글이면, 종성,중성,종성 순서대로 지우자.
                if(KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status == "K")
                {
                    var cho  = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho;
                    var jung = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung;
                    var jong = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong;

                    if( cho != null && jung != null && jong != null ) //초성,중성,종성이 모두 입력된 경우
                    {
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = null; //종성만 지워라.
                        KR_INPUT.make_complete_cur_focus();
                        KR_INPUT.string_make();
                        KR_INPUT.draw_string();
                    }else if (cho != null && jung != null && jong == null) //초성,중성만 입력된 경우라면
                    {
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = null; //중성을 지워라.
                        KR_INPUT.make_complete_cur_focus();
                        KR_INPUT.string_make();
                        KR_INPUT.draw_string();
                    }else //초성만 입력 되었거나, 중성만 입력되었거나 한 상황이면, 확 지워 버려라
                    {
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho      = null; //초성
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung     = null; //중성
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong     = null; //종성
                        KR_INPUT.tmp_focus--;
                        KR_INPUT.string_make();
                        KR_INPUT.draw_string();
                    }
                }
                else
                {
                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null
                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho      = null; //초성
                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung     = null; //중성
                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong     = null; //종성
                    KR_INPUT.tmp_focus--;
                    KR_INPUT.string_make();
                    KR_INPUT.draw_string();
                }
                return;
            break;
        case KeyDefine.left:
        case KR_INPUT.KEY.LEFT: // 20171026.dblee
                //if(KR_INPUT.row_focus == 4 && KR_INPUT.col_focus == 2) break;//'ㅋ'에서 왼쪽key누르면 반응 없게 하자.
                if(KR_INPUT.col_focus >= 2)
                {
                    KR_INPUT.col_focus--;
                    KR_INPUT.draw_focus(before_row,before_col);
                }
                break;
        case KeyDefine.right:
        case KR_INPUT.KEY.RIGHT: // 20171026.dblee
                if(KR_INPUT.mode_kor_eng == "KOR")
                {
                    if(KR_INPUT.row_focus == 4 && KR_INPUT.col_focus == 7) break;//'ㅣ'에서 오른쪽key누르면 반응 없게 하자.
                }
                else //"ENG"
                {
                    //if(KR_INPUT.row_focus == 4 && KR_INPUT.col_focus == 9) break;//'z'에서 오른쪽key누르면 반응 없게 하자.
                }
                if(KR_INPUT.col_focus < KR_INPUT.get_array_num(KR_INPUT.row_focus))
                {
                    KR_INPUT.col_focus++;
                    KR_INPUT.draw_focus(before_row,before_col);
                }
                else if(KR_INPUT.row_focus == 3 && KR_INPUT.col_focus == 9) //'ㅠ'자리에서 오른쪽으로 누르면 back화면으로 이동
                {
                    KR_INPUT.row_focus = 2;
                    KR_INPUT.col_focus++;
                    KR_INPUT.draw_focus(before_row,before_col);
                }

                break;
        case KeyDefine.down:
        case KR_INPUT.KEY.DOWN: // 20171026.dblee
                if(KR_INPUT.row_focus < 6)
                {
                    KR_INPUT.row_focus++;


                    if(KR_INPUT.mode_kor_eng == "KOR")
                    {
                        if(KR_INPUT.row_focus == 3 && KR_INPUT.col_focus == 10) {KR_INPUT.row_focus = 5;KR_INPUT.col_focus=1;} //3행10열은 존재하지 않는다 4행10열로 보낸다.4행10열은 없으므로 5행1열(스페이스)로 보낸다.
                        if(KR_INPUT.row_focus == 4)
                        {
                            switch(KR_INPUT.col_focus)
                            {
                                //case 1:
                                case 8:
                                case 9: KR_INPUT.row_focus = 5;KR_INPUT.col_focus=1; break;
                            }
                        }
                    }
                    else//"ENG"일경우
                    {
                        if(KR_INPUT.row_focus == 3 && KR_INPUT.col_focus == 10) {KR_INPUT.row_focus = 4;KR_INPUT.col_focus=10;} //3행10열은 존재하지 않는다 4행10열로 보낸다.
                        if(KR_INPUT.row_focus == 4)
                        {
                            switch(KR_INPUT.col_focus)
                            {
                               //case 1:
                               // case 8:
                               // case 9: KR_INPUT.row_focus = 5;KR_INPUT.col_focus=1; break;
                            }
                        }
                    }
                    if(KR_INPUT.row_focus == 5) KR_INPUT.col_focus = 1; //space 1개만 있다.
                    if(KR_INPUT.row_focus == 6) KR_INPUT.col_focus = 1; //확인,취소만 있다.
                    KR_INPUT.draw_focus(before_row,before_col);
                }
                break;
        case KeyDefine.up:
        case KR_INPUT.KEY.UP: // 20171026.dblee
                if(KR_INPUT.row_focus >= 2)
                {
                    KR_INPUT.row_focus--;
                    if(KR_INPUT.row_focus == 5) KR_INPUT.col_focus = 1; //space 1개만 있다.
                    if(KR_INPUT.row_focus == 4) KR_INPUT.col_focus = 4; //space에서 up한 경우라면 'ㅍ'으로 옮기자.
                    if(KR_INPUT.row_focus == 3 && KR_INPUT.col_focus == 10) KR_INPUT.row_focus = 2; // back space로 옮겨라.
                    KR_INPUT.draw_focus(before_row,before_col);

                }
                break;
        case KeyDefine.enter:
        case KR_INPUT.KEY.ENTER: // 20171026.dblee
            
                if(KR_INPUT.mode_kor_eng == "KOR")
                {
                    switch(KR_INPUT.row_focus)
                    {
                        case 1:
                                //0,1,2,3,4,5,6,7,8,9
                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                                KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row1[KR_INPUT.col_focus];
                                KR_INPUT.string_make();
                                KR_INPUT.draw_string();
                                break;
                        case 2: //ㄱㄴㄷㄹㅁ ㅏㅑㅓㅕ <-
    /*
                                if(KR_INPUT.col_focus == 1) //한영 전환이면
                                {
                                    //한영 전환 코드 향후에 넣기
                                    return;
                                }
                                else */
                                if(KR_INPUT.col_focus == 10) // <- back space라면 한 글자를 지워라.
                                {
                                    if(KR_INPUT.tmp_focus <= 0) {console.log("empty");return;}

                                    //한글이면, 종성,중성,종성 순서대로 지우자.
                                    if(KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status == "K")
                                    {
                                        var cho  = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho;
                                        var jung = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung;
                                        var jong = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong;

                                        if( cho != null && jung != null && jong != null ) //초성,중성,종성이 모두 입력된 경우
                                        {
                                            KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = null; //종성만 지워라.
                                            KR_INPUT.make_complete_cur_focus();
                                            KR_INPUT.string_make();
                                            KR_INPUT.draw_string();
                                        }else if (cho != null && jung != null && jong == null) //초성,중성만 입력된 경우라면
                                        {
                                            KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = null; //중성을 지워라.
                                            KR_INPUT.make_complete_cur_focus();
                                            KR_INPUT.string_make();
                                            KR_INPUT.draw_string();
                                        }else //초성만 입력 되었거나, 중성만 입력되었거나 한 상황이면, 확 지워 버려라
                                        {
                                            KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null
                                            KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                            KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho      = null; //초성
                                            KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung     = null; //중성
                                            KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong     = null; //종성
                                            KR_INPUT.tmp_focus--;
                                            KR_INPUT.string_make();
                                            KR_INPUT.draw_string();
                                        }
                                    }
                                    else
                                    {
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho      = null; //초성
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung     = null; //중성
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong     = null; //종성
                                        KR_INPUT.tmp_focus--;
                                        KR_INPUT.string_make();
                                        KR_INPUT.draw_string();
                                    }
                                    return;
                                }
                                else //ㄱ,ㄴ,ㄷ,ㄹ,ㅁ,ㅏ,ㅑ,ㅓ,ㅕ
                                {
                                    var str = KR_INPUT.row2[KR_INPUT.col_focus]; //입력한 값
                                    switch(str)
                                    {   //자음의 입력
                                        case "ㄱ":
                                        case "ㄴ":
                                        case "ㄷ":
                                        case "ㄹ":
                                        case "ㅁ":
                                                    KR_INPUT.input_jaeum(str);
                                                    break;
                                        //모음의 입력
                                        case "ㅏ":
                                        case "ㅑ":
                                        case "ㅓ":
                                        case "ㅕ":
                                                    KR_INPUT.input_moeum(str);
                                                    break;
                                    }
                                    KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                    //KR_INPUT.string += KR_INPUT.row2[KR_INPUT.col_focus];
                                }
                                KR_INPUT.draw_string();
                                break;
                        case 3: // ㅂ ㅅ ㅇ ㅈ ㅊ ㅗ ㅛ ㅜ ㅠ
                                var str = KR_INPUT.row3[KR_INPUT.col_focus]; //입력한 값
                                switch(str)
                                {   //자음의 입력
                                    case "ㅂ":
                                    case "ㅅ":
                                    case "ㅇ":
                                    case "ㅈ":
                                    case "ㅊ":
                                                KR_INPUT.input_jaeum(str);
                                                break;
                                    //모음의 입력
                                    case "ㅗ":
                                    case "ㅛ":
                                    case "ㅜ":
                                    case "ㅠ":
                                                KR_INPUT.input_moeum(str);
                                                break;
                                }
                                KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                KR_INPUT.draw_string();
                                break;
                        case 4: // 공백(한/영),ㅋ ㅌ ㅍ ㅎ ㅠ ㅡ ㅣ

                                if(KR_INPUT.col_focus == 1) // 한영 전환 버턴을 눌렀다면
                                {
                                    KR_INPUT.kor_eng_mode_change(); //한영 전환을 진행 하라.
                                    return;
                                }

                                var str = KR_INPUT.row4[KR_INPUT.col_focus]; //입력한 값
                                switch(str)
                                {   //자음의 입력
                                    case "ㅋ":
                                    case "ㅌ":
                                    case "ㅍ":
                                    case "ㅎ":
                                                KR_INPUT.input_jaeum(str);
                                                break;
                                    //모음의 입력
                                    case "ㅡ":
                                    case "ㅣ":
                                                KR_INPUT.input_moeum(str);
                                                break;
                                }
                                KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                KR_INPUT.draw_string();
                                break;
                        case 5: //space bar
                                //현재 작업중인 한글을 종료하라.
                                if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K")
                                {
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                                    KR_INPUT.draw_string();

                                }
                                else
                                {
                                    if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                                    KR_INPUT.tmp_focus++;
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "S"; //Symbol : Space,등 특수문자가 입력 되었다.
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = " ";
                                    KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                    KR_INPUT.draw_string();
                                }
                                break;
                        case 6: //확인, 취소
                                if(KR_INPUT.col_focus == 1) //확인
                                {
                                    if(KR_INPUT.check_validate())
                                    {
                                        //KR_INPUT.init()호출시 입려완료되면 실행될 CallBackFn을 인자로 보내 왔다.
                                        //KR_INPUT.end(); //user_name 중복체크를 위해 .end를 여기서 호출하지 않고 CallBackFn에서 호출함.
                                        KR_INPUT.CallBackFn&KR_INPUT.CallBackFn(KR_INPUT.string);
                                    }
                                }
                                else if(KR_INPUT.col_focus == 2) //취소 -- 전체 지우고 완전 초기화-- 그리고 닫기
                                {
                                    //글자 조합을 위해 필요한 tmp_str을 생성한다. 아래 벼열에 대한 설명은 "자판배열.xls"두번째탭을 참고 바람.
                                    for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
                                    {
                                        KR_INPUT.tmp_str[i]          = {};
                                        KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
                                        KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                        KR_INPUT.tmp_str[i].cho      = null; //초성
                                        KR_INPUT.tmp_str[i].jung     = null; //중성
                                        KR_INPUT.tmp_str[i].jong     = null; //종성
                                    }
                                    KR_INPUT.tmp_focus = 0;
                                    KR_INPUT.string_make();
                                    KR_INPUT.draw_string();

                                    //KR_INPUT.end();
                                    KR_INPUT.CallBackFn&KR_INPUT.CallBackFn("_CLOSE");
                                }
                                else //초기화
                                {
                                    //글자 조합을 위해 필요한 tmp_str을 생성한다. 아래 벼열에 대한 설명은 "자판배열.xls"두번째탭을 참고 바람.
                                    for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
                                    {
                                        KR_INPUT.tmp_str[i]          = {};
                                        KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
                                        KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                        KR_INPUT.tmp_str[i].cho      = null; //초성
                                        KR_INPUT.tmp_str[i].jung     = null; //중성
                                        KR_INPUT.tmp_str[i].jong     = null; //종성
                                    }
                                    KR_INPUT.tmp_focus = 0;
                                    KR_INPUT.string_make();
                                    KR_INPUT.draw_string();

                                    KR_INPUT.CallBackFn&KR_INPUT.CallBackFn("_INIT");
                                }
                                break;
                    }                 
                }
                else if(KR_INPUT.mode_kor_eng == "ENG")//"ENG"일경우
                {
                    switch(KR_INPUT.row_focus)
                    {
                        case 1:
                                //0,1,2,3,4,5,6,7,8,9
                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                                KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row1[KR_INPUT.col_focus];
                                KR_INPUT.string_make();
                                KR_INPUT.draw_string();
                                break;
                        case 2: //ABCDEFGHI <-

                                if(KR_INPUT.col_focus == 10) // <- back space라면 한 글자를 지워라.
                                {
                                    if(KR_INPUT.tmp_focus <= 0) {console.log("empty");return;}
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho      = null; //초성
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung     = null; //중성
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong     = null; //종성
                                    KR_INPUT.tmp_focus--;
                                    KR_INPUT.string_make();
                                    KR_INPUT.draw_string();
                                    return;
                                }
                                else //ABCDEFGHI
                                {
                                    if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice("MAX "+KR_INPUT.MAX_CHAR+" character");return;}
                                    KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row2[KR_INPUT.col_focus];
                                    KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                    KR_INPUT.draw_string();
                                }                                
                                break;
                        case 3: // JKLMNOPQR
                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice("MAX "+KR_INPUT.MAX_CHAR+" character");return;}
                                KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row3[KR_INPUT.col_focus];
                                KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                KR_INPUT.draw_string();
                                break;
                        case 4: // 공백(한/영),STUVWXYZ, a,A

                                if(KR_INPUT.col_focus == 1) // 한영 전환 버턴을 눌렀다면
                                {
                                    KR_INPUT.kor_eng_mode_change(); //한영 전환을 진행 하라.
                                    return;
                                }
                                if(KR_INPUT.col_focus == 10) // 대소문자 전환 버턴을 눌렀다면
                                {
                                    KR_INPUT.aA_mode_change(); //대소문자 전환을 진행 하라.
                                    return;
                                }


                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice("MAX "+KR_INPUT.MAX_CHAR+" character");return;}
                                KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row4[KR_INPUT.col_focus];                             
                                KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                KR_INPUT.draw_string();
                                break;
                        case 5: //space bar
                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                                KR_INPUT.tmp_focus++;
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "S"; //Symbol : Space,등 특수문자가 입력 되었다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = " ";
                                KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                KR_INPUT.draw_string();
                                break;
                        case 6: //확인, 취소
                                if(KR_INPUT.col_focus == 1) //확인
                                {
                                    if(KR_INPUT.check_validate())
                                    {
                                        //KR_INPUT.init()호출시 입려완료되면 실행될 CallBackFn을 인자로 보내 왔다.
                                        //KR_INPUT.end(); //user_name 중복체크를 위해 .end를 여기서 호출하지 않고 CallBackFn에서 호출함.
                                        KR_INPUT.CallBackFn&KR_INPUT.CallBackFn(KR_INPUT.string);
                                    }
                                }
                                else if(KR_INPUT.col_focus == 2) //취소 -- 전체 지우고 완전 초기화-- 그리고 닫기
                                {
                                    //글자 조합을 위해 필요한 tmp_str을 생성한다. 아래 벼열에 대한 설명은 "자판배열.xls"두번째탭을 참고 바람.
                                    for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
                                    {
                                        KR_INPUT.tmp_str[i]          = {};
                                        KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
                                        KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                        KR_INPUT.tmp_str[i].cho      = null; //초성
                                        KR_INPUT.tmp_str[i].jung     = null; //중성
                                        KR_INPUT.tmp_str[i].jong     = null; //종성
                                    }
                                    KR_INPUT.tmp_focus = 0;
                                    KR_INPUT.string_make();
                                    KR_INPUT.draw_string();

                                    //KR_INPUT.end();
                                    KR_INPUT.CallBackFn&KR_INPUT.CallBackFn("_CLOSE");
                                }
                                else //초기화
                                {
                                    //글자 조합을 위해 필요한 tmp_str을 생성한다. 아래 벼열에 대한 설명은 "자판배열.xls"두번째탭을 참고 바람.
                                    for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
                                    {
                                        KR_INPUT.tmp_str[i]          = {};
                                        KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
                                        KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                        KR_INPUT.tmp_str[i].cho      = null; //초성
                                        KR_INPUT.tmp_str[i].jung     = null; //중성
                                        KR_INPUT.tmp_str[i].jong     = null; //종성
                                    }
                                    KR_INPUT.tmp_focus = 0;
                                    KR_INPUT.string_make();
                                    KR_INPUT.draw_string();

                                    KR_INPUT.CallBackFn&KR_INPUT.CallBackFn("_INIT");
                                }

                                break;
                    }  
                }
                else
                {
                    switch(KR_INPUT.row_focus)
                    {
                        case 1:
                                //0,1,2,3,4,5,6,7,8,9
                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                                KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row1[KR_INPUT.col_focus];
                                KR_INPUT.string_make();
                                KR_INPUT.draw_string();
                                break;
                        case 2: //ABCDEFGHI <-

                                if(KR_INPUT.col_focus == 10) // <- back space라면 한 글자를 지워라.
                                {
                                    if(KR_INPUT.tmp_focus <= 0) {console.log("empty");return;}
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho      = null; //초성
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung     = null; //중성
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong     = null; //종성
                                    KR_INPUT.tmp_focus--;
                                    KR_INPUT.string_make();
                                    KR_INPUT.draw_string();
                                    return;
                                }
                                else //ABCDEFGHI
                                {
                                    if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice("MAX "+KR_INPUT.MAX_CHAR+" character");return;}
                                    KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row2[KR_INPUT.col_focus];
                                    KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                    KR_INPUT.draw_string();
                                }                                
                                break;
                        case 3: // JKLMNOPQR
                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice("MAX "+KR_INPUT.MAX_CHAR+" character");return;}
                                KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row3[KR_INPUT.col_focus];
                                KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                KR_INPUT.draw_string();
                                break;
                        case 4: // 공백(한/영),STUVWXYZ, a,A

                                if(KR_INPUT.col_focus == 1) // 한영 전환 버턴을 눌렀다면
                                {
                                    KR_INPUT.kor_eng_mode_change(); //한영 전환을 진행 하라.
                                    return;
                                }
                                if(KR_INPUT.col_focus == 10) // 대소문자 전환 버턴을 눌렀다면
                                {
                                    KR_INPUT.aA_mode_change(); //대소문자 전환을 진행 하라.
                                    return;
                                }


                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice("MAX "+KR_INPUT.MAX_CHAR+" character");return;}
                                KR_INPUT.tmp_focus++; //새로운곳에 숫자를 입력해 봅시다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status   = "N"; //Number
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.row4[KR_INPUT.col_focus];                             
                                KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                KR_INPUT.draw_string();
                                break;
                        case 5: //space bar
                                if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                                KR_INPUT.tmp_focus++;
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "S"; //Symbol : Space,등 특수문자가 입력 되었다.
                                KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = " ";
                                KR_INPUT.string_make(); //tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
                                KR_INPUT.draw_string();
                                break;
                        case 6: //확인, 취소
                                if(KR_INPUT.col_focus == 1) //확인
                                {
                                    if(KR_INPUT.check_validate())
                                    {
                                        //KR_INPUT.init()호출시 입려완료되면 실행될 CallBackFn을 인자로 보내 왔다.
                                        //KR_INPUT.end(); //user_name 중복체크를 위해 .end를 여기서 호출하지 않고 CallBackFn에서 호출함.
                                        KR_INPUT.CallBackFn&KR_INPUT.CallBackFn(KR_INPUT.string);
                                    }
                                }
                                else if(KR_INPUT.col_focus == 2) //취소 -- 전체 지우고 완전 초기화-- 그리고 닫기
                                {
                                    //글자 조합을 위해 필요한 tmp_str을 생성한다. 아래 벼열에 대한 설명은 "자판배열.xls"두번째탭을 참고 바람.
                                    for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
                                    {
                                        KR_INPUT.tmp_str[i]          = {};
                                        KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
                                        KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                        KR_INPUT.tmp_str[i].cho      = null; //초성
                                        KR_INPUT.tmp_str[i].jung     = null; //중성
                                        KR_INPUT.tmp_str[i].jong     = null; //종성
                                    }
                                    KR_INPUT.tmp_focus = 0;
                                    KR_INPUT.string_make();
                                    KR_INPUT.draw_string();

                                    //KR_INPUT.end();
                                    KR_INPUT.CallBackFn&KR_INPUT.CallBackFn("_CLOSE");
                                }
                                else //초기화
                                {
                                    //글자 조합을 위해 필요한 tmp_str을 생성한다. 아래 벼열에 대한 설명은 "자판배열.xls"두번째탭을 참고 바람.
                                    for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
                                    {
                                        KR_INPUT.tmp_str[i]          = {};
                                        KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
                                        KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                        KR_INPUT.tmp_str[i].cho      = null; //초성
                                        KR_INPUT.tmp_str[i].jung     = null; //중성
                                        KR_INPUT.tmp_str[i].jong     = null; //종성
                                    }
                                    KR_INPUT.tmp_focus = 0;
                                    KR_INPUT.string_make();
                                    KR_INPUT.draw_string();

                                    KR_INPUT.CallBackFn&KR_INPUT.CallBackFn("_INIT");
                                }
                                break;
                    }
                }
                break;        
        case KeyDefine.esc: //이전 key누를경우
        case KR_INPUT.KEY.ESC:
        case KeyDefine.back:
        case KR_INPUT.KEY.BACK:
                                KR_INPUT.back();
								//history.back();
								//return;
								
                                //글자 조합을 위해 필요한 tmp_str을 생성한다. 아래 벼열에 대한 설명은 "자판배열.xls"두번째탭을 참고 바람.
                                // for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
                                // {
                                //     KR_INPUT.tmp_str[i]          = {};
                                //     KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
                                //     KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
                                //     KR_INPUT.tmp_str[i].cho      = null; //초성
                                //     KR_INPUT.tmp_str[i].jung     = null; //중성
                                //     KR_INPUT.tmp_str[i].jong     = null; //종성
                                // }
                                // KR_INPUT.tmp_focus = 0;
                                // KR_INPUT.string_make();
                                // KR_INPUT.draw_string();

                                // //KR_INPUT.end();
                                // KR_INPUT.CallBackFn&KR_INPUT.CallBackFn("_CLOSE");
              break;        
    }

    //20190625_ywlee KT에서 이름변경 메뉴에서 back 누르면 종료 팝업 나오는 현상 수정
    try
    {
        e.preventDefault();
        e.stopPropagation();    
    }
    catch (error)
    {
        console.log("Error in KR_INPUT.key_event():"+error);
    }

}

KR_INPUT.back = function()
{    
    // utilNotice("back 키 눌림");
    for(var i=1;i<=KR_INPUT.MAX_CHAR;i++) //0번지 배열을 안쓸끼라.
    {
        KR_INPUT.tmp_str[i]          = {};
        KR_INPUT.tmp_str[i].status   = null; //상태값 K(Korean), E(English), S(Symbol:Space등), N(Number), null, CK( Complete Korean :완료된한글)
        KR_INPUT.tmp_str[i].complete = null; //완성된 글씨, 또는 화면에 표기 되는 것
        KR_INPUT.tmp_str[i].cho      = null; //초성
        KR_INPUT.tmp_str[i].jung     = null; //중성
        KR_INPUT.tmp_str[i].jong     = null; //종성
    }
    KR_INPUT.tmp_focus = 0;
    KR_INPUT.string_make();
    KR_INPUT.draw_string();

    //KR_INPUT.end();
    KR_INPUT.CallBackFn&KR_INPUT.CallBackFn("_CLOSE");
}

// 20260309_dblee 사용자 키 기능 구현(202603091450)
// 이메일이 정규 표현식과 일치하는지 확인
KR_INPUT.is_valid_email = function(email)
{
    // 1. 입력값이 문자열인지 확인
    if (typeof email !== 'string') return false;

    // 2. 더 엄격한 정규 표현식 (영문, 숫자, .-_ 만 허용)
    // ^[a-zA-Z0-9._%+-]+ : 시작은 영문/숫자/허용된 특수문자
    // @[a-zA-Z0-9.-]+    : @ 뒤에도 영문/숫자/.- 만 허용
    // \.[a-zA-Z]{2,}$    : 마지막은 점(.) 뒤에 2글자 이상의 영문자
    var re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    // 이메일이 정규 표현식과 일치하는지 확인
    return re.test(email);
}

//입력한 string의유효성 검사
//성공하면 return true
//실패하면 return false, return false할 대 notic 메시지 꼭 날리기
KR_INPUT.check_validate = function()
{
    //첫번째 문자 공백 테스트
    if( KR_INPUT.tmp_str[1].complete ==' ')
    {
        if(KR_INPUT.mother_lang == "KOR")
            KR_INPUT.notice("첫문자로 공백을 사용 할 수 없습니다.");
        else
            KR_INPUT.notice("You can not use spaces as the first character.");

        return false;
    }

    //마지막 문자 공백 테스트
    if( KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete ==' ')
    {
        if(KR_INPUT.mother_lang == "KOR")
            KR_INPUT.notice("마지막 문자로 공백을 사용 할 수 없습니다.");
        else
            KR_INPUT.notice("You can not use spaces as the last character.");        
        return false;
    }

    if(KR_INPUT.check_not_allowed(KR_INPUT.string))
    {
        if(KR_INPUT.mother_lang == "KOR")
            KR_INPUT.notice("해당 문자는 사용할 수 없습니다.");
        else
            KR_INPUT.notice("These characters are not allowed.");
        return false;
    }

    if(KR_INPUT.check_str)
    {
        //최소 입력 길이 테스트
        if(KR_INPUT.tmp_focus < KR_INPUT.MIN_CHAR)
        {
            if(KR_INPUT.mother_lang == "KOR")
                KR_INPUT.notice("최소 ^0자 이상은 입력 하셔야 합니다.".replace("^0", KR_INPUT.MIN_CHAR));
            else
            KR_INPUT.notice("You must enter at least ^0 characters.".replace("^0", KR_INPUT.MIN_CHAR));
            return false;
        }
        // 20260309_dblee 사용자 키 기능 구현(202603091450)
        if (!KR_INPUT.email_check)
        {
            if(KR_INPUT.string == KR_INPUT.before_str)
            {
                if(KR_INPUT.mother_lang == "KOR")
                    KR_INPUT.notice("기존의 이름과 같습니다.");
                else
                    KR_INPUT.notice("Same as previous name.");
                return false;
            }
        }
    }
    
    return true;
}

//비속어 욕문자 등 테스트
KR_INPUT.check_not_allowed = function(str)
{
    var NOT_ALLOWED =[

        //공개적인단어
        "부싯돌","오광전맞고","엘도라도","에어포스","부싯","부시",
        "딜라이브","씨제이헬로","케이티",

        //숫자
        "18년","18놈","18ㄴ","28년","28놈","28ㄴ",
        "10탱",

        //욕설 ㄱ,ㄴ,ㄷ,ㄹ
        "개새끼","개년","개자","걸레","고추","꼬추","게임","겜",
        "넘","놈",
        "뒈져","뒤질레","개또라이","또라이","디진다","더러운","똥",

        //욕설 ㅁ,ㅂ,ㅅ,ㅇ
        "뭘봐","미친",
        "보지","보쥐","빠구리","병신","븅신","바보","발럼",
        "사기","섹스","씨발","씨벌","씨팔","씨블","씨불","시발","시벌","시블","시불","시팔","시펄","십탱","씨방세","씨방새","씹","쌩매장","생매장","앂","쉬발",
        "운영자","운영",
        "처먹어라","처먹어","쳐먹",

        //욕설 ㅈ,ㅊ,ㅋ,ㅌ,ㅍ,ㅎ
        "조까","좆","좃","좃까","좃가","졸라","자지","잠지","좃을까","좆을","좃을","짜샤","쨔샤","짜사","쨔사",

        //욕설 ㄱ,ㄴ,ㄷ,ㄹ,ㅁ,ㅂ,ㅅ,ㅇ,ㅈ,ㅊ,ㅋ,ㅌ,ㅍ,ㅎ
        "ㄱ","ㄴ","ㄷ","ㄹ","ㅁ","ㅂ","ㅅ","ㅇ","ㅈ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ",
        "ㅏ","ㅑ","ㅓ","ㅕ","ㅗ","ㅛ","ㅜ","ㅠ","ㅡ","ㅣ",

        //공개적인 영어단어
        "busidol","incredible","intank",/*"eldorado",*/

        //a,b,c,d,e,f,g
        "ass","bastard","bitch","boob","cock","cunt","damn","dick","dummy","faggot","fuc","frek","hella",
        "idiot","lol","nigga","penis","pussy","redneck","shit","stupid","suck","tit","whore",
        "sex",
        "arse","autism","autistic",
        "bastard","bellend",
        "crazy",
        'none', 'null', 'undefined',
        

        //" "//공백문자(스페이스 허용안함) --> 공백문자를 허용하고, 처음시작의 공백문자만 허용 안함.
        ];

    // 20260309_dblee 사용자 키 기능 구현(202603091450)
    // 20260312_dblee 이메일 형식인지 체크를 한다.
    if (KR_INPUT.email_check)
    {
        return !(KR_INPUT.is_valid_email(str));
    }
    else
    {
        if(!KR_INPUT.use_special_char)
        {
            NOT_ALLOWED = NOT_ALLOWED.concat(["!", "@", "#", "$", "%", "&", "=", "_", "-","/",  ",",   ".",   "*",   "+",   "~"]);
        }

        var len = NOT_ALLOWED.length;
        var match = null;

        str = str.toLowerCase(); //대문자가 있다면 소문자로 바꾸어라.
        str = str.replace(/\s/gi,''); //모든 공백'Space'을 제거하라. 첫문장 공백은 validate에서 체크 함.

        for(i=0;i<len;i++)
        {
            if(str.indexOf(NOT_ALLOWED[i]) != -1) // indexOf --찾는 문자열이 없다면 -1을 return한다. 즉 != -1 이면은 찾는 문자열이 있다면 이라는 뜻이다.
                return true;
        }
    }
    return false;
}

//모음 ch가 입력 되었다. ㅏ,ㅑ,ㅓ,ㅕ.....
KR_INPUT.input_moeum = function(ch)
{

    if( KR_INPUT.tmp_focus == 0 ||      //최소 시작이거나
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status != "K" || //앞에 입력이 한글이 아니거나
        (KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho  == null && //또는 중성만 입력된 경우라면
         KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung != null &&
         KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong == null )
            )
    {
        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
        KR_INPUT.tmp_focus++;
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = ch;
    }
    //현재 tmp_focus에 초성만 입력 되었다면
    //즉 "ㄱ + ㅏ" 입력된 경우 "가"로 처리 하기
    else if( KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho != null &&
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung == null )
    {

        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
        KR_INPUT.make_complete_cur_focus();
        //KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.get_unicode(KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho,ch);
        //return KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete;
    }
    //초성,중성이 입력된 상태에서 또다시 모움이 입력 되었다면
    //즉, " 고 + ㅏ"입력된 경우 "과"로 처리 하기
    else if( KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho  != null &&
             KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung != null &&
             KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong == null )
    {
        //먼저 입력된 중성
        switch(KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung)
        {
            case 'ㅏ':
                        switch(ch)
                        {
                            case 'ㅣ': //ㅐ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅐ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
            case 'ㅑ':
                        switch(ch)
                        {
                            case 'ㅣ': //ㅒ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅒ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
            case 'ㅓ':
                        switch(ch)
                        {
                            case 'ㅣ': //ㅔ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅔ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
            case 'ㅕ':
                        switch(ch)
                        {
                            case 'ㅣ': //ㅖ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅖ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
            case 'ㅗ':
                        switch(ch)
                        {
                            case 'ㅏ': //ㅘ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅘ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅣ': //외
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅚ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
            case 'ㅘ':
                        switch(ch)
                        {
                            case 'ㅣ': //외
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅙ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
            case 'ㅜ':
                        switch(ch)
                        {
                            case 'ㅓ': //ㅝ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅝ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅣ': //ㅟ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅟ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
            case 'ㅝ':
                        switch(ch)
                        {
                            case 'ㅣ': //ㅞ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅞ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
            case 'ㅡ':
                        switch(ch)
                        {
                            case 'ㅣ': //ㅢ
                                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung ="ㅢ";KR_INPUT.make_complete_cur_focus();return;
                        }break;
        }

        //"와 + ㅏ" 입력의 경우 다음 배열로 넘긴다.
        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
        KR_INPUT.tmp_focus++; //
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
        return;
    }
    //현재 tmp_focus에 종성까지 입력된 경우라면 마지막 종성을 다음 초성으로 옮기고, 중성을 입력 한다.
    //즉 "간 + ㅏ" 입력된 경우 "가나"로 처리 하기
    else if( KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho  != null &&
             KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung != null &&
             KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong != null )
    {
        //혹 종성이 자음두개로 합쳐진것이면 분리해 줘야 한다.
        switch(KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong)
        {
            case 'ㄲ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄱ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㄱ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㄳ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄱ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅅ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㄵ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄴ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅈ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㄶ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄴ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅎ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㄺ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄹ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㄱ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㄻ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄹ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅁ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㄼ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄹ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅂ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㄽ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄹ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅅ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㄾ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄹ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅌ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        break;
            case 'ㄿ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄹ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅍ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㅀ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㄹ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅎ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㅄ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㅂ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅅ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
            case 'ㅆ':
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = 'ㅅ';
                        KR_INPUT.make_complete_cur_focus();
                        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
                        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
                        KR_INPUT.tmp_focus++;
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = 'ㅅ';
                        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung = ch;
                        KR_INPUT.make_complete_cur_focus();
                        return;
        }
        if(KR_INPUT.tmp_focus + 1 > KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}

        KR_INPUT.tmp_str[KR_INPUT.tmp_focus+1].cho = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong;
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = null;
        KR_INPUT.make_complete_cur_focus(); //현재 tmp_focus의 내용을 기반으로 글자를 다시 만들어 complete에 넣어라.
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus+1].jung = ch;
        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
        KR_INPUT.tmp_focus++;
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
        KR_INPUT.make_complete_cur_focus(); //현재 tmp_focus의 내용을 기반으로 글자를 다시 만들어 complete에 넣어라.
    }

}

//최대 0자 까지 입력할 수 있습니다.
KR_INPUT.get_notice_input_max = function()
{
    if(KR_INPUT.mode_kor_eng == "KOR")
        return "최대 "+KR_INPUT.MAX_CHAR+"자까지 입력할 수 있습니다.";
    else
        return "Up to "+KR_INPUT.MAX_CHAR+" characters can be input";
}

//자음 ch가 입력 되었다. ㄱ,ㄴ,ㄷ,ㄹ....
KR_INPUT.input_jaeum = function(ch)
{
    //최초 시작이면 초성이다.
    if( KR_INPUT.tmp_focus == 0 ||
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status != "K" || //방금입력한 문자가 한글이 아니면 새롭게 작성한다.
        //중성만 입력 된 경우
        (KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho  == null &&
         KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung != null &&
         KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong == null)
      )
    {
        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
        KR_INPUT.tmp_focus++; //이제 새로운거 한개 입력 하자
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = ch;
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = ch;
    }
    //초성만 들어 있는데, 또 자음이 들어 왔다. 이것는 쌍자음이거나, 아니면 focus++해 줘야 한다.
    else if(  KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho  != null &&
              KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung == null &&
              KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong == null)
    {
        //쌍자음(초성) 입력 체크 : ㅃ ㅉ ㄸ ㄲ ㅆ
        var cho = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho;
        if(cho == ch)//입력 문자가 같으면
        {
            switch(cho)
            {
                case "ㅂ": KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho ="ㅃ"; return;
                case "ㅈ": KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho ="ㅉ"; return;
                case "ㄷ": KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho ="ㄸ"; return;
                case "ㄱ": KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho ="ㄲ"; return;
                case "ㅅ": KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho ="ㅆ"; return;
            }

        }
        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
        KR_INPUT.tmp_focus++;
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = ch;
        KR_INPUT.make_complete_cur_focus();
    }
    //초성과(cho)와 중성(jung)이  다 들어 있다면 종성이다
    else if(  KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho  != null &&
              KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung != null &&
              KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong == null)
    {
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong = ch;
        KR_INPUT.make_complete_cur_focus();
    }
    //초성,중성,종성 모두 다 들어 있다면
    else if(  KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho  != null &&
              KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung != null &&
              KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong != null)
    {
        //쌍자음 받침일지 체크한다.
        var jong = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong;
        switch(jong)
        {
            case "ㄱ": // ㄲ,ㄳ
                        switch(ch)
                        {
                            case 'ㄱ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄲ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅅ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄳ";KR_INPUT.make_complete_cur_focus();return;
                        }
                        break;
            case "ㄴ": // ㄵ, ㄶ
                        switch(ch)
                        {
                            case 'ㅈ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄵ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅎ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄶ";KR_INPUT.make_complete_cur_focus();return;
                        }
                        break;
            case "ㄹ": // 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ'
                        switch(ch)
                        {
                            case 'ㄱ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄺ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅁ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄻ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅂ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄼ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅅ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄽ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅌ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄾ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅍ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㄿ";KR_INPUT.make_complete_cur_focus();return;
                            case 'ㅎ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㅀ";KR_INPUT.make_complete_cur_focus();return;
                        }
                        break;
            case "ㅂ": // ㅄ
                        switch(ch)
                        {
                            case 'ㅅ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㅄ";KR_INPUT.make_complete_cur_focus();return;
                        }
                        break;
            case "ㅅ": // ㅄ
                        switch(ch)
                        {
                            case 'ㅅ': KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong ="ㅆ";KR_INPUT.make_complete_cur_focus();return;
                        }
                        break;
        }
        if(KR_INPUT.tmp_focus != 0 && KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status =="K") KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "CK";
        if(KR_INPUT.tmp_focus >= KR_INPUT.MAX_CHAR) {console.log("input max!");KR_INPUT.notice(KR_INPUT.get_notice_input_max());return;}
        KR_INPUT.tmp_focus++;
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].status = "K";
        KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho = ch;
        KR_INPUT.make_complete_cur_focus();
    }
}

//현재 tmp_focus의 내용을 기반으로 글자를 다시 만들어 complete에 넣어라.
KR_INPUT.make_complete_cur_focus = function()
{
    var cho  = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].cho;
    var jung = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jung;
    var jong = KR_INPUT.tmp_str[KR_INPUT.tmp_focus].jong;

    var unicode = KR_INPUT.get_unicode(cho,jung,jong);
    KR_INPUT.tmp_str[KR_INPUT.tmp_focus].complete = unicode;
}

//tmp_str에 들어 있는 내용을 취합해서 string에 넣는다.
KR_INPUT.string_make = function()
{
    var str ="";
    for(var i=1;i<=KR_INPUT.tmp_focus;i++)
    {
        str += KR_INPUT.tmp_str[i].complete;
    }
    KR_INPUT.string = str;
}

//현재 string을 화면에 그려 준다.
KR_INPUT.draw_string = function()
{
    var len = KR_INPUT.string.length;
    var last_k ="";//마지막 한글
    var str = KR_INPUT.string;

    //끝 글자가 한글이면 색상 바꿔주기
    if( len >= 1 && KR_INPUT.tmp_str[len].status == "K")
    {
         str = KR_INPUT.string.substr(0,len-1); //끝에 한글을 잘라 낸다.
         last_k = "<font color=#ff7e00>"+KR_INPUT.tmp_str[len].complete+"</font>";
    }

    //공백은 &nbsp로 치환 하기
    str = str.replace(/\ /g, "&nbsp"); //공백을 &nbsp로 치환 하라.

    KR_INPUT.make_css('#KIdiv_input_window', {
        'line-height'   : '55px',
        'font-size'     : '33px',
        'color'         : '#191818',
        'text-align'    : 'center',
        //'text-shadow'   : '1px 1px 1px yellow',
        'font-family'   :'sans-serif',
        position    : 'absolute'
    }).innerHTML = str+last_k+"<font color=red>_</font>";
}
//focus를 그린다.
KR_INPUT.draw_focus = function(before_row,before_col)
{
    //기존 focus unfocus시키고
    var ida;
    var bgcolor;
    switch(before_row)
    {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
               ida = "KIdiv_row"+before_row+"_"+before_col;
            //    var tmp_ch = eval("KR_INPUT.row"+before_row+"[before_col]");
               var tmp_ch = KR_INPUT['row'+before_row][before_col];
            
               bgcolor = KR_INPUT.get_bg(tmp_ch);
               break;
        case 6:
               ida = "KIdiv_btn_"+before_col;
               bgcolor = "#596b77";
               break;
    }



    KR_INPUT.make_css('#'+ida, {
        background     : bgcolor,
        'box-shadow'   : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
        'border-radius': '5px',
        'border'       : 'none'
    });

    //해당 버턴 focus 시키기
    var id;
    switch(KR_INPUT.row_focus)
    {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
               id = "KIdiv_row"+KR_INPUT.row_focus+"_"+KR_INPUT.col_focus;
               break;
        case 6:
               id = "KIdiv_btn_"+KR_INPUT.col_focus;
               break;
    }

    KR_INPUT.make_css('#'+id, {
        //background      : 'red',
        'box-shadow' : '0px 0px 10px 3px #00f6ff',
        'border-radius': '8px',
        'border'     : '3px solid #ffffff'
    });

    if( KR_INPUT.blink_timer != null )
    {
        clearInterval(KR_INPUT.blink_timer); KR_INPUT.blink_timer = null;
    }
    KR_INPUT.blink_timer = setTimeout(KR_INPUT.unblink_focus,500);
}

//현재 focus되어 있는 놈에 깜빡임 부여
KR_INPUT.blink_focus = function()
{
    var id;
    switch(KR_INPUT.row_focus)
    {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
               id = "KIdiv_row"+KR_INPUT.row_focus+"_"+KR_INPUT.col_focus;
               break;
        case 6:
               id = "KIdiv_btn_"+KR_INPUT.col_focus;
               break;
    }

    KR_INPUT.make_css('#'+id, {
        //background      : 'red',
        'box-shadow' : '0px 0px 10px 3px #00f6ff',
        'border-radius': '8px',
        'border'     : '3px solid #ffffff'
    });

    if( KR_INPUT.blink_timer != null )
    {
        clearInterval(KR_INPUT.blink_timer); KR_INPUT.blink_timer = null;
    }
    KR_INPUT.blink_timer = setTimeout(KR_INPUT.unblink_focus,900);

    //console.log("KR_INPUT.blink_focus()");
}

//현재 focus되어 있는 놈에 깜빡임 부여
KR_INPUT.unblink_focus = function()
{
    var id;
    switch(KR_INPUT.row_focus)
    {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
               id = "KIdiv_row"+KR_INPUT.row_focus+"_"+KR_INPUT.col_focus;
               break;
        case 6:
               id = "KIdiv_btn_"+KR_INPUT.col_focus;
               break;
    }

    //unblink
    KR_INPUT.make_css('#'+id, {
        'box-shadow'   : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
        'border-radius': '5px',
        'border'       : 'none'
    });

    if( KR_INPUT.blink_timer != null )
    {
        clearInterval(KR_INPUT.blink_timer); KR_INPUT.blink_timer = null;
    }
    KR_INPUT.blink_timer = setTimeout(KR_INPUT.blink_focus,400);

    //console.log("KR_INPUT.unblink_focus()");

}

//해당 행의끝을 return한다.
KR_INPUT.get_array_num = function(row)
{
    switch(row)
    {
        case 1: return KR_INPUT.row1.length - 1;
        case 2: return KR_INPUT.row2.length - 1;
        case 3: return KR_INPUT.row3.length - 1;
        case 4: return KR_INPUT.row4.length - 1;
        case 5: return KR_INPUT.row5.length - 1;
        case 6: return KR_INPUT.has_init_btn ? 3 : 2; //버턴 2개;
    }
}

//========================================================

//초성(cho_c),중성(jung_c),종성(jong_c)을 받아서 해당 한글을 조합하여 return한다.
//cho_c  : 초성 character형 즉, "ㄱ"
//jung_c : 중성 character형 즉, "ㅏ"
//jong_c : 종성 character형 즉, "ㅁ"

KR_INPUT.get_unicode = function(cho_c,jung_c,jong_c)
{
    var cho_i   = -1;   //초성 인텍스
    var jung_i  = -1;   //중성 인덱스
    var jong_i  = -1;   //종성 인덱스

    //초성의 인텍스를 찾는다.
    for(var i=0;i<19;i++) //KR_INPUT.cho.length
    {
        if(cho_c == KR_INPUT.cho[i])
        {
            cho_i = i;
            break; //루핑을 빠져 나가자
        }
    }
    if(cho_i == -1) console.log("초성을 찾을수 없습니다.:"+cho_c);

    //중성의 인텍스를 찾는다.
    for(var i=0;i<21;i++) //KR_INPUT.jung.length
    {
        if(jung_c == KR_INPUT.jung[i])
        {
            jung_i = i;
            break; //루핑을 빠져 나가자
        }
    }
    if(jung_i == -1)
    {
        console.log("중성을 찾을수 없습니다.:"+jung_c);
        return cho_c; //초성만 return한다.
    }

    //종성의 인텍스를 찾는다.
    for(var i=0;i<28;i++) //KR_INPUT.jong.length
    {
        if(jong_c == KR_INPUT.jong[i])
        {
            jong_i = i;
            break; //루핑을 빠져 나가자
        }
    }
    if(jong_i == -1)
    {
        if(jong_c != null)
            console.log("중성을 찾을수 없습니다.:"+jung_c);
        else
            jong_i = 0; //종성이 없는 경우 처리
    }

    //초성, 중성, 종성의 인텍스가 확인되면 그 값을 출력하라.
    var unicode = 44032 + (cho_i * 588) + (jung_i * 28) + jong_i;
    var str     = String.fromCharCode(unicode);

    return str;
}

//===================================================
//한영 전환을 하라.
KR_INPUT.kor_eng_mode_change = function()
{
    if(KR_INPUT.mode_kor_eng == "KOR")    KR_INPUT.mode_kor_eng = "ENG";
    else if(KR_INPUT.mode_kor_eng == "ENG")    KR_INPUT.mode_kor_eng = "#+=";
    else                                    KR_INPUT.mode_kor_eng = "KOR";

    //모드 바꾸었으니 배열값을 바꿔주자.
    KR_INPUT.row_change();

    //다시 그리자
    KR_INPUT.make_screen();
    
}

//대소문자 전환을 하라.
KR_INPUT.aA_mode_change = function()
{
    if(KR_INPUT.mode_aA == "a")    KR_INPUT.mode_aA = "A";
    else                        KR_INPUT.mode_aA = "a";

    //모드 바꾸었으니 배열값을 바꿔주자.
    KR_INPUT.row_change();

    //다시 그리자
    KR_INPUT.make_screen();
    
}


//현재 모드에 맞게 row2,3,4의 배열값을 정의 한다.
KR_INPUT.row_change = function()
{
    
    if(KR_INPUT.mode_kor_eng == "KOR")
    {
        KR_INPUT.row2 = ["",  "ㄱ",     "ㄴ",   "ㄷ",   "ㄹ",   "ㅁ",   "ㅏ",   "ㅑ",   "ㅓ",   "ㅕ",   "←"];
        KR_INPUT.row3 = ["",  "ㅂ",     "ㅅ",   "ㅇ",   "ㅈ",   "ㅊ",   "ㅗ",   "ㅛ",   "ㅜ",   "ㅠ"];
        KR_INPUT.row4 = ["",  "ENG",       "ㅋ",   "ㅌ",   "ㅍ",   "ㅎ",   "ㅡ",   "ㅣ",   "",     "",     ""];
    }
    else if(KR_INPUT.mode_kor_eng == "ENG") //KR_INPUT.mode_kor_eng == "ENG"
    {
        if(KR_INPUT.mode_aA == "A") //대문자 이면
        {
            KR_INPUT.row2 = ["",  "A",     "B",   "C",   "D",   "E",   "F",   "G",   "H",   "I",   "←"];
            KR_INPUT.row3 = ["",  "J",     "K",   "L",   "M",   "N",   "O",   "P",   "Q",   "R"];
            KR_INPUT.row4 = ["",  "#+=", "S",   "T",   "U",   "V",   "W",   "X",   "Y",   "Z",     "Lower case"];
        }
        else //KR_INPUT.mode_aA == "a" //소문자이면
        {
            KR_INPUT.row2 = ["",  "a",     "b",   "c",   "d",   "e",   "f",   "g",   "h",   "i",   "←"];
            KR_INPUT.row3 = ["",  "j",     "k",   "l",   "m",   "n",   "o",   "p",   "q",   "r"];
            KR_INPUT.row4 = ["",  "#+=", "s",   "t",   "u",   "v",   "w",   "x",   "y",   "z",     "Upper case"];
        }

    }
    else
    {
        KR_INPUT.row2 = ["", "!", "@", "#", "$", "%", "&", "=", "_", "-", "←"];
        KR_INPUT.row3 = ["",  "/",  ",",   ".",   "*",   "+",   "~",   "",   "",   ""];
        KR_INPUT.row4 = ["",  "KOR", "",   "",   "",   "",   "",   "",   "",   "",  ""];

    }
}

KR_INPUT.set_has_init_btn = function(boolean)
{
    KR_INPUT.has_init_btn = boolean;

    if(boolean)
    {
        KR_INPUT.make_css('#KIdiv_btn_3', {
            left            : '949px',
            top             : '594px',
            width           : '125px',
            height          : '60px',
            background      : '#596b77',
            'line-height'   : '60px',
            'font-size'     : '35px',
            'color'         : '#ffffff',
            'text-align'    : 'center',
            'border-radius' : '5px',
            'opacity'       : 0.85,
            'box-shadow'    : '1px 1px 1px #2c3439, 1px 1px 1px #8b949b inset',
            position    : 'absolute'
        }).innerHTML =  (KR_INPUT.mother_lang == "KOR")? "초기화":"Init";
    }
}

KR_INPUT.set_check_str = function(boolean)
{
    KR_INPUT.check_str = boolean;
}

KR_INPUT.set_special_char = function(boolean)
{
    KR_INPUT.use_special_char = boolean;
}

KR_INPUT.fitToViewport = function () {
  var baseW = 1280;
  var baseH = 720;

  // 기준: parentEl이 있으면 그 크기, 없으면 윈도우
  var vw = KR_INPUT.parentEl ? KR_INPUT.parentEl.clientWidth  : Math.max(document.documentElement.clientWidth,  window.innerWidth || 0);
  var vh = KR_INPUT.parentEl ? KR_INPUT.parentEl.clientHeight : Math.max(document.documentElement.clientHeight, window.innerHeight || 0);

  // 화면에 꽉 차도록(양쪽 레터박스 허용) 최소 스케일 선택
  var scale = Math.min(vw / baseW, vh / baseH);

  // 가운데 정렬 오프셋
  var left = Math.floor((vw - baseW * scale) / 2);
  var top  = Math.floor((vh - baseH * scale) / 2);

  // 루트 컨테이너에 스케일 적용
  KR_INPUT.make_css('#KR_INPUT_div', {
    width:  baseW + 'px',
    height: baseH + 'px',
    transform: 'translate(' + left + 'px,' + top + 'px) scale(' + scale + ')',
    'transform-origin': '0 0',
    position: 'absolute' // 고정
  });

  // 팝업 배경(검은막)도 루트 크기 기준이므로 그대로 두면 됨
};

// 리스너 바인딩/해제(선택)
KR_INPUT.fitToViewport = function () {
  var baseW = 1280, baseH = 720;

  var vw = Math.max(document.documentElement.clientWidth,  window.innerWidth || 0);
  var vh = Math.max(document.documentElement.clientHeight, window.innerHeight || 0);

  var scale = Math.min(vw / baseW, vh / baseH);
  var left  = Math.floor((vw - baseW * scale) / 2);
  var top   = Math.floor((vh - baseH * scale) / 2);

  // 스케일은 '본체'에만
//   KR_INPUT.make_css('#KR_INPUT_widow_div', {
//     transform: 'translate(' + left + 'px,' + top + 'px) scale(' + scale + ')',
//     'transform-origin': '0 0'
//   });
};

// 리스너(한 번만 바인딩)
if (!KR_INPUT._resizeBound) {
  KR_INPUT._onResize = function(){ KR_INPUT.fitToViewport(); };
  window.addEventListener('resize', KR_INPUT._onResize);
  window.addEventListener('orientationchange', KR_INPUT._onResize);
  KR_INPUT._resizeBound = true;
}