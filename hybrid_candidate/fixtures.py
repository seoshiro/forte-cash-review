"""Generated diagrams and explicitly fictional text; never dataset-derived."""
from PIL import Image,ImageDraw,ImageFont
from cashreview.video import Sample


CASES=[
    {'name':'fictional_departure_ongoing','left':True,'service':'ongoing','expected':('clear','left','ongoing','sufficient'),'match':'R22'},
    {'name':'fictional_stayed_ongoing','left':False,'service':'ongoing','expected':('clear','stayed','ongoing','sufficient'),'match':'no_event'},
    {'name':'fictional_departure_completed','left':True,'service':'completed','expected':('clear','left','completed','sufficient'),'match':'no_event'},
    {'name':'fictional_unknown_service','left':True,'service':'unclear','expected':('clear','left','unclear','insufficient'),'match':'no_event'}]


def text(case):
    movement='crosses beyond the marked work-area boundary between frames2 and3' if case['left'] else 'stays within the marked working area in every frame, briefly standing up'
    service={'ongoing':'is explicitly visibly ongoing and unfinished throughout the supplied sequence','completed':'is explicitly visibly completed before departure','unclear':'cannot be established from the supplied context; the client is only standing nearby'}[case['service']]
    return ('FICTIONAL CONTROL, not a real video. The four supplied frame descriptions establish the cashier operating the station and the clearly marked work area. '
        'The operator '+movement+'. Client service '+service+'. '
        'For supported facts use frame indices0 and3. For ambiguous service use context insufficient. No hidden information is available.')


def frames(case):
    try:font=ImageFont.truetype('arial.ttf',16)
    except OSError:font=ImageFont.load_default(size=16)
    result=[];positions=[(110,240),(110,180),(110,100),(280,40)] if case['left'] else [(110,240),(110,220),(110,200),(110,220)]
    for index,(x,y) in enumerate(positions):
        image=Image.new('RGB',(384,384),'white');draw=ImageDraw.Draw(image)
        draw.rectangle((10,60,230,375),outline='black',width=4);draw.text((20,345),'WORK AREA',fill='black',font=font)
        draw.rectangle((222,170,242,300),fill='gray');draw.ellipse((294,225,326,257),fill='blue')
        draw.text((270,270),'CLIENT',fill='blue',font=font)
        draw.ellipse((x-14,y-14,x+14,y+14),fill='red');draw.text((max(2,x-35),max(2,y-35)),'CASHIER',fill='red',font=font)
        status={'ongoing':'SERVICE: ONGOING','completed':'SERVICE: COMPLETED','unclear':'SERVICE: UNKNOWN'}[case['service']]
        draw.text((15,5),status,fill='black',font=font)
        result.append(Sample(float(index*2),image))
    return result
