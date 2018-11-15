#!/usr/bin/env python3


############################################################
# (C) Aaron Vose 2018 -- GPLv3
############################################################


#
# Standard modules
#
import argparse
import math
import subprocess
import os
import time
import warnings
#
# Heavy-lifting modules
#
import imageio
import numpy
from skimage import transform
#
# Parallel compute modules
#
import dask
from dask.diagnostics import ProgressBar
#
# GUI modules
#
import threading
import tkinter
from PIL import Image, ImageTk


############################################################
############################################################


QRGA_VERSION   = "0.6"
QRGA_COPYRIGHT = "Copyright (C) 2018 Aaron Vose"


########################################


WORST_ERROR  = 1.0e20
UPDATE_DELAY = 0.5


############################################################
############################################################


def read_image(inf="qrga_tmp.png"):
    img = None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        img = imageio.imread(inf)
    img = img.astype(float)
    img = img / 255.0
    return img


########################################


def write_image(img,outf="qrga_tmp.png"):
    img = numpy.copy(img*255.0).astype('uint8')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        imageio.imwrite(outf,img)


########################################


def write_distorted_image(img,outf="qrga_tmp.png"):
    #
    # Pad to avoid edge issues when transforming
    #
    pw = int(img.shape[0]/2)
    ph = int(img.shape[1]/2)
    big = numpy.pad(img,((pw,pw),(ph,ph)),'constant',constant_values=((1,1),(1,1)))
    #
    # Increase resolution to help with aliasing
    #
    w = big.shape[0]*3
    h = big.shape[1]*3
    big = transform.resize(big, (w,h), anti_aliasing=False, mode='constant')
    #
    # Apply transform(s)
    #
    magnitude = 0.1 + numpy.random.uniform()*0.2
    afine_tf = transform.AffineTransform(shear=magnitude)
    big = transform.warp(big, inverse_map=afine_tf, mode='constant', cval=1.0)
    #
    # Write the distorted image
    #
    write_image(big,outf=outf)

        
############################################################
############################################################


def qr_encode(data, outf="qrga_tmp.png", qr_size=10):
    #
    # Build command / arg list and run "qrencode" util
    #
    command =  ["qrencode"]
    command += ["-o",outf]
    command += ["-m","0"]
    command += ["--foreground","000000FF"]
    command += ["--background","FFFFFFFF"]
    command += ["-v","%d"%qr_size]
    command += ["-l","H"]
    command += [data]
    subprocess.call( command )
    #
    # Read in and return the resultant image
    #
    current = read_image(outf)
    return current


########################################


def qr_decode(inf="qrga_tmp.png"):
    #
    # Build command / arg list and run "zbarimg" util
    #
    command =  ["zbarimg"]
    command += ["--quiet"]
    command += ["--raw"]
    command += [inf]
    devnull = open(os.devnull, 'w')
    try:
        data = subprocess.check_output( command, stderr=devnull )
    except:
        return None
    #
    # Parse and return the data / failure
    #
    data = data.decode('utf-8')
    data = str(data)
    data = data.rstrip("\n")
    return data


########################################


def qr_diff(target,mask,current):
    #
    # Diff at original scale
    #
    delta = numpy.absolute(target - current)
    delta = delta * mask
    err = numpy.sum( delta )
    #
    # Diff at half scale
    #
    w = int(target.shape[0]/2)
    h = int(target.shape[1]/2)
    s_target  = transform.resize(target,  (w,h), anti_aliasing=True, mode='constant')
    s_mask    = transform.resize(mask,    (w,h), anti_aliasing=True, mode='constant')
    s_current = transform.resize(current, (w,h), anti_aliasing=True, mode='constant')
    s_delta = numpy.absolute(s_target - s_current)
    s_delta = s_delta * s_mask
    s_err = numpy.sum( s_delta )
    #
    # Return average of large and small scale diffs
    #
    return (err+(s_err*4.0)) / 2.0


########################################


def qr_validate(in_data=None,img=None,fn=None,rm=True,distort=False,qr_size=10):
    #
    # Get a temp filename if needed.
    #
    if fn is None:
        rnd = numpy.random.randint(2**30)
        fn = "qrga_tmp_%d.png"%rnd
    #
    # Encode / write if needed
    #
    if img is not None:
        if distort is True:
            write_distorted_image(img,fn)
        else:
            write_image(img,fn)
    else:
        img = qr_encode(in_data,outf=fn,qr_size=qr_size)
        if distort is True:
            write_distorted_image(img,fn)
    #
    # Try to decode to verify
    #
    out_data = qr_decode(inf=fn)
    if rm is True:
        subprocess.call(["rm",fn])
    #
    # Return result
    #
    return img if out_data == in_data else None


############################################################
############################################################


def eval_nonce(nonce,data,target,mask,qr_size):
    #
    # Encode with nonce / padding
    #
    rnd = numpy.random.randint(2**30)
    tf = "qrga_tmp_%d.png"%rnd
    padding = "?nonce=0x%X"%nonce
    in_data = data + padding
    current = qr_encode(in_data,outf=tf,qr_size=qr_size)
    subprocess.call(["rm",tf])
    #
    # Compute error w.r.t. target image
    #
    err = qr_diff(target, mask, current)
    return (in_data, err)


########################################


def nonce_search(args,target,mask,gui):
    print("Start nonce search (%d):"%args.nsearch)
    if gui:
        msg = "Nonce Search (%.1f%s)\n\n"%(0.0,"%")
        gui.update(text=msg)
    min_dat = args.data
    min_err = WORST_ERROR
    max_err = 0.0
    sum_err = 0.0
    batchsz = 100
    nbatch  = int(args.nsearch / batchsz)
    current = None
    for i in range(0,nbatch):
        #
        # Eval a batch of nonces
        #
        tstart = time.time()
        print("  Nonce search chunk %d/%d (%.1f%s):"%(i,nbatch,(i/float(nbatch))*100,"%"))
        results = [ dask.delayed(eval_nonce)(i*batchsz+j, args.data, target, mask, args.qrver) for j in range(0,batchsz) ]
        with ProgressBar(dt=UPDATE_DELAY):
            results = dask.compute(*results, scheduler='threads')
        #
        # Process batch results
        #
        for result in results:
            in_data = result[0]
            err = result[1]
            if err < WORST_ERROR:
                sum_err += err
                max_err = err if err > max_err else max_err
                if err < min_err:
                    #
                    # Verify a decode
                    #
                    current = qr_validate(in_data=in_data,qr_size=args.qrver)
                    if current is None:
                        print("    Decode error: '%s' not found."%(in_data))
                        continue
                    #
                    # Save as a valid new best
                    #
                    min_err = err
                    min_dat = in_data
                    write_image(current,args.output)
        tend = time.time()
        #
        # Progress print
        #
        print("  Nonce search iteration %d:"%((i+1)*batchsz))
        print("    Min data:  '%s'"%min_dat)
        pct = 100.0 * (min_err / numpy.sum(mask))
        print("    Min error: %f %s"%(min_err,("%0.4f"%(pct))+"%"))
        print("    Max error: %f"%max_err)
        print("    Avg error: %f"%(sum_err/float((i+1)*batchsz)))
        print("    Time:      %f s (per nonce)"%((tend-tstart)/float(batchsz)))
        print("")
        if gui:
            msg =  "Nonce Search (%.1f%s)\n\n"%(((i+1)/float(nbatch))*100,"%")
            msg += "Nonce:  %s\n"%(min_dat.replace(args.data+"?nonce=",""))
            msg += "Min:  %.2f  %.2f%s\n"%(min_err,pct,"%")
            msg += "Max:  %.4f\n"%max_err
            msg += "Avg:  %.4f\n"%(sum_err/float((i+1)*batchsz))
            msg += "Time:  %.4f s / nonce\n"%((tend-tstart)/float(batchsz))
            best = target*mask + (current*(1.0-mask))
            gui.update(data=current,best=best,text=msg)
        #
        # Return best
        #
    return min_dat


############################################################
############################################################


def eval_ind(ind,data,target,mask,qr_size,nvalidation):
    #
    # Validate image decode
    #
    ntests = nvalidation if nvalidation else 1
    distort = True if nvalidation > 0 else False
    for i in range(0,ntests):
        if qr_validate(in_data=data,img=ind,distort=distort,qr_size=qr_size) is None:
            return WORST_ERROR
    #
    # Compare images for fitness
    #
    err = qr_diff(target, mask, ind)
    return err


########################################


def ga_search(args,target,mask,founder,data,gui):
    print("Start genetic algorithm search (%d):"%args.gens)
    if gui:
        gui.update(text="Genetic Algorithm Search")
    #
    # Create initial population
    #
    first = qr_encode(data,qr_size=args.qrver)
    population = [ numpy.copy(founder) for i in range(0,args.popsz) ]
    #
    # Generation loop
    #
    best = population[0]
    if gui:
        gui.update(data=best)
    for gen in range(0,args.gens):
        tstart = time.time()
        #
        # Stdout print
        #
        print("  Generation %d:"%gen)
        print("    PopSize: %d"%len(population))
        #
        # Compute fitness for population members
        #
        fits = [ dask.delayed(eval_ind)(i,data,target,mask,args.qrver,args.validate) for i in population ]
        with ProgressBar(dt=0.5):
            fits = dask.compute(*fits, scheduler='threads')
        tfend = time.time()
        viable = sum(fit != WORST_ERROR for fit in fits)
        #        
        # Viability selection
        #
        if viable is 0:
            print("    Population went extinct!")
            break
        print("    nViable: %d"%viable)
        indexes = list(range(len(fits)))
        indexes.sort(key=fits.__getitem__)
        fits = list(map(fits.__getitem__, indexes))
        population = list(map(population.__getitem__, indexes))
        pct = 100.0 * (fits[0] / numpy.sum(mask))
        print("    Fitness: %.1f %s"%(fits[0],("%.4f"%(pct))+"%"))
        best = population[0]
        write_image(best,args.output)
        if args.save:
            write_image(best,"%s_gen%d.png"%(os.path.splitext(args.target)[0],gen))
            delta = numpy.absolute((target - population[0])*mask)
            write_image(delta,"%s_err.png"%(os.path.splitext(args.target)[0]))
        population = population[0:int(args.popsz*args.sigma)]
        #
        # Reproduction with mutation
        #
        opop = len(population)
        while len(population) < args.popsz:
            i = numpy.random.randint(0,opop)
            #j = numpy.random.randint(0,opop)
            #indj = numpy.copy( population[j] )
            ind = numpy.copy( population[i] )
            #mask = numpy.ones_like(ind)
            #mask[:int(mask.shape[0]/2)] = 0.0
            #ind = numpy.copy( ind*mask + indj*(1.0-mask) )
            for j in range(0,int(ind.shape[0]*ind.shape[1]*args.mu)):
                x = numpy.random.randint(0,ind.shape[0])
                y = numpy.random.randint(0,ind.shape[1])
                if mask[x][y]:
                    mu_mode = numpy.random.randint(0,10)
                    if mu_mode < 1:
                        #
                        # 10%: Set to QR code's pixel
                        #
                        ind[x][y] = first[x][y]
                    if mu_mode < 6:
                        #
                        # 50%: Set to target image's pixel
                        #
                        ind[x][y] = target[x][y]
                    if mu_mode < 9:
                        #
                        # 30%: Invert pixel
                        #
                        ind[x][y] = 1.0 - ind[x][y]
                    else:
                        #
                        # 10%: Random pixel value
                        #
                        ind[x][y] = numpy.random.uniform()
            population.append( ind )
        #
        # End of generation timing and print.
        #
        tend = time.time()
        print("    Time:    %.2f s (fit %.3f, ga %.3f)"%(tend-tstart,tfend-tstart,tend-tfend))
        if gui:
            msg =  "Genetic Algorithm Search\n\n"
            msg += "Generation:  %d\n"%gen
            msg += "PopSize:  %d\n"%len(population)
            msg += "Viable:  %d\n"%viable
            msg += "Fit:  %.2f  %.2f%s\n"%(fits[0],pct,"%")
            msg += "Time:  %.2f s\n\n"%(tend-tstart)
            gui.update(data=best,text=msg)
    #
    # Return best found
    #
    return best


############################################################
############################################################


def eval_intensity(target,mask,image,lth,uth):
    l = float(lth) / 255.0
    u = float(uth) / 255.0
    mtarget = target * mask
    mabove = numpy.select( [mtarget > u], [ 1.0 ] )
    mbelow = numpy.select( [mtarget < l], [ 1.0 ] ) * mask
    cimage = numpy.clip(image, l, 1.0)*mabove + image*(1.0-mabove)*mask + image*(1.0-mask)
    cimage = numpy.clip(cimage,0.0, u)*mbelow + image*(1.0-mbelow)*mask + image*(1.0-mask)
    err = qr_diff(target,mask,cimage)
    return (err, cimage, lth, uth)


########################################


def batch(l, n):
    for i in range(0, len(l), n):
        yield l[i:i+n]


########################################

        
def intensity_search(args,target,mask,image,data,gui):
    print("Start intensity search")
    if gui:
        gui.update(text="Intensity Search")
    #
    # Search lower ("black") + upper ("white") bounds without overlap
    #
    merr = WORST_ERROR
    ml = 0
    mu = 0
    min_img = image
    thresholds = []
    for l in range(0,256):
        for u in range(l+1,256):
            thresholds.append( (l,u) )
    thresholds = numpy.random.permutation(thresholds)
    #
    # Process in chunks
    #
    chunks = list(batch(thresholds, 1000))
    for c, chunk in enumerate(chunks):
        #
        # Eval chunk and look for new minimum error
        #
        errs = [ dask.delayed(eval_intensity)(target,mask,image,t[0],t[1]) for t in chunk ]
        with ProgressBar(dt=0.5):
            errs = dask.compute(*errs, scheduler='threads')
        for err, img, l, u in errs:
            if err < merr:
                if qr_validate(data,img=img,qr_size=args.qrver) is not None:
                    merr = err
                    ml = l
                    mu = u
                    min_img = numpy.copy(img)
        #
        # Progress print / update after each chunk is done
        #
        print("  Intensity Search: chunk %d of %d"%(c,len(chunks)))
        print("    min err: %f  (@ %d %d)"%(merr,ml,mu))
        if gui:
            pct = (float(c+1)*100.0) / float(len(chunks))
            msg =  "Intensity Search (%.1f%s)\n\n"%(pct,"%")
            msg += "Error: %f\n"%merr
            msg += "Lower: %d\nUpper: %d"%(ml,mu)
            gui.update(data=min_img,text=msg)
    #
    # Intensity search is done
    #
    print("  Intensity Search: done.")
    print("  min err: %f  (@ %d %d)"%(merr,ml,mu))
    print("")
    #
    # Return best found
    #
    return min_img


############################################################
############################################################


class gui_window():
    def __init__(self,data,best,text,lock):
        #
        # Save lock, set initial data
        #
        self.lock = lock
        self.data = numpy.copy(data)
        self.best = numpy.copy(best)
        self.text = str(text)
        #
        # Setup window and canvas
        #
        self.root = tkinter.Tk()
        self.root.title("QRGA v%s"%(QRGA_VERSION))
        self.cwidth  = self.data.shape[0]*3+5
        self.cheight = self.data.shape[1]+3
        self.frame = tkinter.Frame(self.root, width=self.cwidth,height=self.cheight)
        self.frame.pack()
        self.canvas = tkinter.Canvas(self.frame, width=self.cwidth,height=self.cheight, background="#000000")
        self.canvas.place(x=0,y=0)
        #
        # Add images
        #
        self.im = Image.frombytes('L',(self.data.shape[1],self.data.shape[0]),self.data.astype('b').tostring())
        self.photo = ImageTk.PhotoImage(image=self.im)
        self.image  = self.canvas.create_image(2,2,image=self.photo,anchor=tkinter.NW)
        self.bim = Image.frombytes('L',(self.best.shape[1],self.best.shape[0]),self.best.astype('b').tostring())
        self.bphoto = ImageTk.PhotoImage(image=self.bim)
        self.bimage = self.canvas.create_image(self.data.shape[0]+3,2,image=self.bphoto,anchor=tkinter.NW)
        #
        # Add text
        #
        green = "#00FF00"
        textx = self.data.shape[0]+3 + self.best.shape[0]+2
        self.ctext = self.canvas.create_text(textx,2,text=self.text,fill=green,anchor=tkinter.NW,justify=tkinter.LEFT)
        self.root.update()
        self.canvas.after(int(UPDATE_DELAY*1000),self.redraw)

    def redraw(self):
        #
        # Grab new data
        #
        self.lock.acquire()
        data = numpy.copy(self.data)
        best = numpy.copy(self.best)
        text = str(self.text)
        self.lock.release()
        #
        # Update GUI
        #
        self.im = Image.frombytes('L',(data.shape[1],data.shape[0]),data.astype('b').tostring())
        self.photo = ImageTk.PhotoImage(image=self.im)
        self.canvas.itemconfig(self.image, image=self.photo)
        self.bim = Image.frombytes('L',(best.shape[1],best.shape[0]),best.astype('b').tostring())
        self.bphoto = ImageTk.PhotoImage(image=self.bim)
        self.canvas.itemconfig(self.bimage, image=self.bphoto)
        self.canvas.itemconfig(self.ctext, text=text)
        self.root.update()
        #
        # Setup another update tick
        #
        self.canvas.after(int(UPDATE_DELAY*1000),self.redraw)


########################################


class gui_thread(threading.Thread):
    def __init__(self,data,best,text):
        #
        # Init the thread, create lock, copy starting data
        #
        threading.Thread.__init__(self)
        self.lock = threading.Lock()
        self.data = numpy.copy(data*255.0)
        self.best = numpy.copy(best*255.0)
        self.text = str(text)
        self.lock.acquire()

    def run(self):
        #
        # Create the GUI window, mark done, start event loop
        #
        self.win = gui_window(self.data,self.best,self.text,self.lock)
        self.lock.release()
        self.win.root.mainloop()
        #
        # GUI was closed, exit.
        #
        print("\n\nGUI closed: exiting.\n")
        os._exit(0)

    def update(self,data=None,text=None,best=None):
        #
        # Lock and update data
        #
        self.lock.acquire()
        if data is not None:
            self.data = numpy.copy(data*255.0)
            self.win.data = self.data
        if text is not None:
            self.text = str(text)
            self.win.text = self.text
        if best is not None:
            self.best = numpy.copy(best*255.0)
            self.win.best = self.best
        self.lock.release()

    def wait_init(self):
        #
        # Wait until the GUI is done with setup
        #
        self.lock.acquire()
        self.lock.release()


########################################


def start_gui(img,best):
    #
    # Start the GUI
    #
    gt = gui_thread(img,best,"Init...")
    gt.start()
    gt.wait_init()
    return gt


############################################################
############################################################


def qrga_init(args):
    #
    # Check special options first
    #
    if args.version:
        print("QRGA version %s"%QRGA_VERSION)
        print("%s"%QRGA_COPYRIGHT)
        exit()        
    if args.info:
        print("QRGA version %s"%QRGA_VERSION)
        print("%s"%QRGA_COPYRIGHT)
        subprocess.call(["qrencode","--version"])
        for i in range(1,41):
            test = qr_encode(QRGA_VERSION,qr_size=i)
            print("  QRv%d: %d x %d"%(i,test.shape[0],test.shape[1]))
        zbv = subprocess.check_output(["zbarimg","--version"])
        zbv = str(zbv.decode('utf-8')).rstrip("\n")
        print("zbarimg version %s"%zbv)
        exit()        
    #
    # Sanity check the encode / decode
    #
    in_data = args.data if args.data else QRGA_VERSION+" "+QRGA_COPYRIGHT
    current = qr_validate(in_data=in_data,qr_size=args.qrver)
    if current is None:
        print("Sanity check failed ('%s' != '%s')!"%(args.data,out_data))
        exit()
    print("Sanity check passed!")
    print("  %d x %d"%(current.shape[0],current.shape[1]))    
    #
    # Open input target image / mask
    #
    if args.target is None:
        print("--target needed! (see --help)")
        exit()
    if args.output is None:
        print("--output needed! (see --help)")
        exit()
    if args.data is None:
        print("--data needed! (see --help)")
        exit()
    target = read_image(args.target)
    print("Target image:")
    print("  %d x %d"%(target.shape[0],target.shape[1]))
    if args.mask is None:
        print("  Warning: --mask not provided, using mask of all ones!")
        mask = numpy.ones(target.shape)
    else:
        mask = read_image(args.mask)
    err = qr_diff(target, mask, current)
    pct = 100.0 * (err / numpy.sum(mask))
    print("  Initial error: %0.1f %s"%(err,("%0.4lf"%(pct))+"%"))
    print("")
    print("Genetic algorithm settings:")
    print("  PopSize:     %d"%(args.popsz))
    print("  Generations: %d"%(args.gens))
    print("  Mutation:    %f  (%.1f px)"%(args.mu,(current.shape[0]*current.shape[1])*args.mu))
    print("  Selection:   %f  (top %.1f)"%(args.sigma,args.popsz*args.sigma))
    print("  Validations: %d  (distort:%s)"%(args.validate if args.validate else 1, str(args.validate > 0)))
    print("")
    #
    # Generate a best-case image
    #
    best = target*mask + (current*(1.0-mask))
    write_image(best,"%s_best.png"%(os.path.splitext(args.target)[0]))
    #
    # Start GUI if needed
    #
    gui = start_gui(current,best) if args.gui else None
    #
    # Return the target image
    #
    return target, mask, gui


########################################


def parse_args():
    parser = argparse.ArgumentParser(description='QRGA'+' v'+QRGA_VERSION+' '+QRGA_COPYRIGHT)
    parser.add_argument('--verbose', action='store_true',        help='verbose flag')
    parser.add_argument('--save',    action='store_true',        help='save intermidiates')
    parser.add_argument('--version', action='store_true',        help='print version and exit')
    parser.add_argument('--info',    action='store_true',        help='print info and exit')
    parser.add_argument('--gui',     action='store_true',        help='enable GUI')
    parser.add_argument('--output',  default=None,   type=str,   help='output result image path')
    parser.add_argument('--target',  default=None,   type=str,   help='desired target image path')
    parser.add_argument('--mask',    default=None,   type=str,   help='target mask image path')
    parser.add_argument('--data',    default=None,   type=str,   help='data payload string (URL)')
    parser.add_argument('--resume',  default=None,   type=str,   help='resume GA with founder')
    parser.add_argument('--qrver',   default=10,     type=int,   help='QR code version (size)')
    parser.add_argument('--nsearch', default=10000,  type=int,   help='nonce search iterations')    
    parser.add_argument('--sigma',   default=0.1,    type=float, help='selection strength')
    parser.add_argument('--mu',      default=0.0015, type=float, help='mutation rate')
    parser.add_argument('--gens',    default=10000,  type=int,   help='generations')
    parser.add_argument('--popsz',   default=100,    type=int,   help='population size')
    parser.add_argument('--validate',default=3,      type=int,   help='QR validations per ind')
    args = parser.parse_args()
    return args


########################################


def main():
    #
    # Pass 0: Parse command line and init
    #
    args = parse_args()
    target, mask, gui = qrga_init(args)
    #
    # Pass 1: padding / nonce search for data
    #
    if args.resume:
        min_dat = qr_decode(inf=args.resume)
        print("Resume with data from QR: '%s'"%min_dat)
        print("")
    else:
        min_dat = nonce_search(args,target,mask,gui)
    image = qr_encode(min_dat,qr_size=args.qrver)
    #
    # Pass 2: intensity search
    #
    if not args.resume:
        image = intensity_search(args,target,mask,image,min_dat,gui)
    #
    # Pass 3: genetic algorithm
    #
    if args.resume:
        image = read_image(args.resume)
    best = target*mask + (image*(1.0-mask))
    write_image(best,"%s_best.png"%(os.path.splitext(args.target)[0]))
    if gui:
        gui.update(best=best)
    ga_best = ga_search(args,target,mask,image,min_dat,gui)
    
    
########################################


if __name__== "__main__":
    main()


############################################################
############################################################