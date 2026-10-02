from html import escape
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator, FuncFormatter
from ui.charts.chart_hover import ChartHover


class ZoneYieldChart(FigureCanvasQTAgg):
    """Fixed six-zone quantity bars with a Yield line on the right axis."""
    def __init__(self, parent=None):
        self.figure = Figure(
            figsize=(9, 3.6), dpi=100, facecolor='white',
            edgecolor='#BFBFBF', linewidth=1.0, frameon=True,
        )
        super().__init__(self.figure)
        self.setParent(parent)
        self.setFixedSize(900, 360)
        self.setStyleSheet('border:1px solid #BFBFBF;background:white;')
        self.fail_axis = self.figure.add_subplot(111)
        self.yield_axis = self.fail_axis.twinx()
        self.hover = ChartHover(self)

    def show_empty_state(self, message):
        self.hover.clear()
        self.fail_axis.clear(); self.yield_axis.clear(); self.figure.legends.clear()
        self.fail_axis.text(.5,.5,message,ha='center',va='center',transform=self.fail_axis.transAxes,color='#777')
        self.fail_axis.set_xticks([]); self.fail_axis.set_yticks([]); self.yield_axis.set_yticks([])
        self.draw_idle()

    def update_chart(self, result):
        if not result or not result.rows:
            self.show_empty_state('Chọn EQP và Handler rồi bấm SEARCH.')
            return
        self.hover.clear()
        self.fail_axis.clear(); self.yield_axis.clear(); self.figure.legends.clear()
        rows = result.rows; positions = list(range(len(rows)))
        bars = self.fail_axis.bar(positions,[r.fail_qty for r in rows],width=.3,color='#5B9BD5',label='Fail',zorder=3)
        yields = [r.yield_percent if r.yield_percent is not None else 0 for r in rows]
        line = self.yield_axis.plot(positions,yields,color='#ED7D31',marker='o',markerfacecolor='white',
                                    markersize=5,linewidth=1.8,label='Yield',zorder=4)[0]
        self.fail_axis.set_title(f'Zone Yield by Handler | EQP: {result.eqpid} | Handler: {result.handler}',
                                 fontsize=12,color='#777',pad=18)
        self.fail_axis.set_ylabel('Fail Qty',fontsize=9)
        self.yield_axis.set_ylabel('Yield',fontsize=9)
        self.yield_axis.yaxis.set_label_position('right')
        self.yield_axis.yaxis.tick_right()
        self.yield_axis.tick_params(labelright=True,labelleft=False)
        self.fail_axis.set_xticks(positions); self.fail_axis.set_xticklabels([r.zone for r in rows])
        self.fail_axis.set_xticks([i-.5 for i in range(7)],minor=True)
        self.fail_axis.set_xlim(-.5,5.5)
        top=max(1,max(r.fail_qty for r in rows))
        ticks=MaxNLocator(nbins=5,integer=True).tick_values(0,top*1.08)
        self.fail_axis.set_yticks(ticks); self.fail_axis.set_ylim(0,ticks[-1])
        lower=max(0,min(yields)-.03); upper=min(100,max(yields)+.03)
        if upper-lower < .1:
            lower=max(0,lower-.05); upper=min(100,upper+.05)
        self.yield_axis.set_ylim(lower,upper)
        self.yield_axis.yaxis.set_major_formatter(FuncFormatter(lambda value,pos:f'{value:.2f}%'))
        self.fail_axis.set_axisbelow(True)
        self.fail_axis.grid(axis='y',color='#E0E0E0',linewidth=.6)
        self.fail_axis.grid(axis='x',which='minor',color='#E0E0E0',linewidth=.6)
        for axis in (self.fail_axis,self.yield_axis):
            axis.tick_params(axis='both',length=0,labelsize=9,colors='#444')
            for spine in axis.spines.values():
                spine.set_color('#BFBFBF'); spine.set_linewidth(.7)
        self.fail_axis.tick_params(axis='x',which='minor',length=0)
        for position,value in zip(positions,yields):
            self.yield_axis.annotate(f'{value:.2f}%',(position,value),xytext=(0,10),textcoords='offset points',
                                     ha='center',fontsize=9,annotation_clip=False)
        texts=[]
        for row in rows:
            percent='0.00% (không có sản lượng)' if row.yield_percent is None else f'{row.yield_percent:.2f}%'
            values=[('EQP',result.eqpid),('Handler',result.handler),('Zone',row.zone),('In',f'{row.in_qty:,}'),
                    ('Pass',f'{row.pass_qty:,}'),('Fail Qty',f'{row.fail_qty:,}'),('Yield',percent)]
            texts.append('<br>'.join(f'<b>{escape(k)}:</b> {escape(str(v))}' for k,v in values))
        self.hover.add_bars(bars,texts); self.hover.add_line(line,texts)
        self.figure.legend([bars,line],['Fail','Yield'],loc='lower center',ncol=2,frameon=False,fontsize=9)
        self.figure.subplots_adjust(left=.085,right=.89,top=.79,bottom=.19)
        self.draw_idle()
