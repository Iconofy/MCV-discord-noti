from flask import Flask
app = Flask(__name__)

dash_html = """
<body id="courseville-body">
<div class="course-section" id="course-section"><a href="?q=courseville/course/81802&amp;from=home" class="course-link">
                    <div class="course-container" id="81802">
                        <div class="course-info">
                            <div class="course-content">
                                <div>2110204 (2026/1)</div>
                                <div class="course-title">Discrete Structures [Section 51 - 54 &amp; 59]</div>
                            </div>
                        </div>
                    </div>
                    </a>
                    <a href="?q=courseville/course/86973&amp;from=home" class="course-link">
                    <div class="course-container" id="86973">
                        <div class="course-info">
                            <div class="course-content">
                                <div>2110104 (2026/1)</div>
                                <div class="course-title">Computer Programming [Section 51 - 55]</div>
                            </div>
                        </div>
                    </div>
                    </a>
</div>
<div class="cv-active-panel cvui-colorset-2 revealed">  <div class="cv-header">    <div class="cv-active-panel-header-img-play"><img src="sites/all/modules/courseville/pict/cvlogo_white_125.png"></div>    <div class="cv-control"><span class="cv-fa-button cv-active-panel-close-button"><i class="fa fa-times"></i></span></div>  </div>  <div class="cv-body">    <div data-role="viewport" class="no-scrollbar"><div class="cv-item">
  <div data-col="left">
  </div>
  <div data-col="right">
    
  </div>
  <div data-col="middle">
    <span style="color:black;background-color:#9CFF00;padding:2px 10px;border-radius:4px">2 items due in 7 days.</span>
  </div>
</div>
<div class="cv-item">
  <div data-col="left">
  </div>
  <div data-col="right">
    <a target="_blank" href="http://localhost:5000/worksheet/81802/2084326"><span class="cv-fa-button"><i class="fa fa-chevron-circle-right"></i></span></a>
  </div>
  <div data-col="middle">
    <span class="cvui-course-badge">2110204</span> <strong>“ส่ง Link Certificate Module 8”</strong> dues in <strong>31 hours</strong>
  </div>
</div>
<div class="cv-item">
  <div data-col="left">
  </div>
  <div data-col="right">
    <a target="_blank" href="http://localhost:5000/worksheet/86973/2120875"><span class="cv-fa-button"><i class="fa fa-chevron-circle-right"></i></span></a>
  </div>
  <div data-col="middle">
    <span class="cvui-course-badge">2110104</span> <strong>“SA7 Self Assessment”</strong> dues in <strong>22 hours</strong>
  </div>
</div>
</div>  </div></div>
</body>
"""

task1_html = """
<body class="courseville-body courseville-worksheet">
<span class="sr-only">Out on 02 October 2026 Due on 08 October 2026 [due] at 09:00</span>
<div id="courseville-worksheet-work-save" class="cvui-margin-v" mode="worksheet">
    <div class="cvui-section-title cvui-margin-v">Submit your work </div><button id="courseville-worksheet-work-save-button" class="btn btn-primary cv-bs" assignment_id="2084326" student_id="6933117321" group_id="-1" data-saving-msg="Saving">Save / Submit</button>    <span id="courseville-worksheet-work-save-spinner" style="display: none;"></span>    <span id="courseville-worksheet-work-status" aria-live="assertive">The latest submission was made at 06-10-2026 13:20:34    </span>  </div>
</body>
"""

task2_html = """
<body class="courseville-body courseville-worksheet">
<span class="sr-only">Out on 24 September 2026 Due on 07 October 2026 [due] at 23:59</span>
<div id="courseville-worksheet-work-save" class="cvui-margin-v" mode="worksheet"><!-- locked || prevented-->    <span id="courseville-worksheet-work-save-spinner" style="display: none;"></span>    <span id="courseville-worksheet-work-status" aria-live="assertive">The latest submission was made at 26-09-2026 05:58:36    </span>  </div>
</body>
"""

@app.route('/home')
def home():
    return dash_html

@app.route('/worksheet/81802/2084326')
def task1():
    return task1_html

@app.route('/worksheet/86973/2120875')
def task2():
    return task2_html

if __name__ == '__main__':
    app.run(port=5000)
